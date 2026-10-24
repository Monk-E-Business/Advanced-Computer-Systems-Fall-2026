// winstat.cpp - Windows helper for the SSD profiling harness (g++, MSYS2 UCRT64).
//
// Provides what Linux exposes through /proc and /sys: cumulative per-volume or
// per-disk I/O counters (the /proc/diskstats equivalent), drive temperature,
// device description, the disk a path lives on, file-cache purging, and
// creation of "never written" files for the misleading-setup experiment.
//
// Every query opens the device with ZERO access rights, which Windows allows
// without elevation for these IOCTLs. Only `purge-standby` needs an
// elevated (Run as administrator) shell.
//
//   winstat isadmin                      -> 1 | 0   (elevated token?)
//   winstat resolve <path>               -> key=value lines: where <path> lives
//   winstat counters <device>            -> "<reads> <bytes_read> <writes> <bytes_written>"
//                                           device = \\?\Volume{...} | D: | PhysicalDriveN
//   winstat temp <disk#>                 -> temperature in deg C, or NA
//   winstat info <disk#>                 -> JSON description of the physical disk
//   winstat mkunwritten <path> <bytes>   -> new file with EOF at <bytes>, no data written
//   winstat purge-standby                -> flush modified list, purge standby list (empties file cache)
//
// Output always uses '\n' line endings (stdout is switched to binary mode) so
// bash $(...) captures are clean.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winioctl.h>

#include <fcntl.h>
#include <io.h>

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <regex>
#include <string>
#include <vector>

namespace {

// ---------------------------------------------------------------------------
// Structures for newer storage properties, declared locally so the tool builds
// with any mingw-w64 header version. Layouts follow the Windows SDK.
// ---------------------------------------------------------------------------
constexpr int kStorageDeviceWriteCacheProperty = 4;
constexpr int kStorageAccessAlignmentProperty = 6;
constexpr int kStorageDeviceSeekPenaltyProperty = 7;
constexpr int kStorageDeviceTrimProperty = 8;
constexpr int kStorageDeviceTemperatureProperty = 52;

struct WriteCacheProperty {
  DWORD Version, Size;
  int WriteCacheType, WriteCacheEnabled, WriteCacheChangeable, WriteThroughSupported;
  BOOLEAN FlushCacheSupported, UserDefinedPowerProtection, NVCacheEnabled;
};
struct AccessAlignment {
  DWORD Version, Size, BytesPerCacheLine, BytesOffsetForCacheAlignment, BytesPerLogicalSector,
      BytesPerPhysicalSector, BytesOffsetForSectorAlignment;
};
struct SeekPenalty { DWORD Version, Size; BOOLEAN IncursSeekPenalty; };
struct TrimDescriptor { DWORD Version, Size; BOOLEAN TrimEnabled; };
struct TemperatureInfo {
  WORD Index;
  SHORT Temperature, OverThreshold, UnderThreshold;
  BOOLEAN OverThresholdChangable, UnderThresholdChangable, EventGenerated;
  BYTE Reserved0;
  DWORD Reserved1;
};
struct TemperatureDescriptor {
  DWORD Version, Size;
  SHORT CriticalTemperature, WarningTemperature;
  WORD InfoCount;
  BYTE Reserved0[2];
  DWORD Reserved1[2];
  TemperatureInfo Info[1];
};

// GUID of the Microsoft Reserved partition, created automatically on GPT disks.
const GUID kMsrGuid = {0xE3C9E316, 0x0B5C, 0x4DB8, {0x81, 0x7D, 0xF9, 0x2D, 0xF0, 0x02, 0x15, 0xAE}};

// ---------------------------------------------------------------------------
class Handle {
 public:
  explicit Handle(HANDLE h = INVALID_HANDLE_VALUE) : h_(h) {}
  ~Handle() { if (valid()) CloseHandle(h_); }
  Handle(const Handle&) = delete;
  Handle& operator=(const Handle&) = delete;
  bool valid() const { return h_ != INVALID_HANDLE_VALUE && h_ != nullptr; }
  HANDLE get() const { return h_; }
 private:
  HANDLE h_;
};

std::string device_path(const std::string& name) {
  if (name.rfind("\\\\", 0) == 0) return name;  // already \\.\X or \\?\Volume{...}
  return "\\\\.\\" + name;                       // "D:" or "PhysicalDrive1"
}

HANDLE open_query(const std::string& name) {
  std::string p = device_path(name);
  while (p.size() > 4 && p.back() == '\\') p.pop_back();  // volume GUID paths must not end in '\'
  return CreateFileA(p.c_str(), 0, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, 0, nullptr);
}

bool query_property(HANDLE h, int id, std::vector<BYTE>& out) {
  STORAGE_PROPERTY_QUERY q{};
  q.PropertyId = static_cast<STORAGE_PROPERTY_ID>(id);
  q.QueryType = PropertyStandardQuery;
  out.assign(4096, 0);
  DWORD n = 0;
  if (!DeviceIoControl(h, IOCTL_STORAGE_QUERY_PROPERTY, &q, sizeof(q), out.data(),
                       static_cast<DWORD>(out.size()), &n, nullptr))
    return false;
  out.resize(n);
  return n > 0;
}

std::string json_escape(const std::string& s) {
  std::string o;
  for (char c : s) {
    if (c == '"' || c == '\\') { o += '\\'; o += c; }
    else if (static_cast<unsigned char>(c) < 0x20) o += ' ';
    else o += c;
  }
  return o;
}

std::string trim(std::string s) {
  while (!s.empty() && (s.back() == ' ' || s.back() == '\0')) s.pop_back();
  size_t i = 0;
  while (i < s.size() && s[i] == ' ') ++i;
  return s.substr(i);
}

std::string descriptor_string(const std::vector<BYTE>& buf, DWORD offset) {
  if (offset == 0 || offset >= buf.size()) return "";
  return trim(reinterpret_cast<const char*>(buf.data() + offset));
}

const char* bus_name(int bus) {
  switch (bus) {
    case 1: return "SCSI";   case 3: return "ATA";    case 7: return "USB";
    case 8: return "RAID";   case 10: return "SAS";   case 11: return "SATA";
    case 12: return "SD";    case 13: return "MMC";   case 14: return "Virtual";
    case 15: return "FileBackedVirtual";            case 16: return "StorageSpaces";
    case 17: return "NVMe";  case 18: return "SCM";   case 19: return "UFS";
    default: return "Other";
  }
}

// Disk number(s) under a volume. Returns -1 on failure.
int volume_disk(const std::string& vol, int* extents = nullptr) {
  Handle h(open_query(vol));
  if (!h.valid()) return -1;
  std::vector<BYTE> buf(sizeof(VOLUME_DISK_EXTENTS) + 16 * sizeof(DISK_EXTENT));
  DWORD n = 0;
  if (!DeviceIoControl(h.get(), IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS, nullptr, 0, buf.data(),
                       static_cast<DWORD>(buf.size()), &n, nullptr))
    return -1;
  auto* e = reinterpret_cast<VOLUME_DISK_EXTENTS*>(buf.data());
  if (extents) *extents = static_cast<int>(e->NumberOfDiskExtents);
  return e->NumberOfDiskExtents > 0 ? static_cast<int>(e->Extents[0].DiskNumber) : -1;
}

std::string volume_guid_for(const std::string& mount_point) {  // "D:\" -> "\\?\Volume{...}\"
  char guid[MAX_PATH] = {0};
  if (!GetVolumeNameForVolumeMountPointA(mount_point.c_str(), guid, MAX_PATH)) return "";
  return guid;
}

int system_disk_number(std::string* system_volume_guid = nullptr) {
  char win[MAX_PATH] = {0};
  GetSystemWindowsDirectoryA(win, MAX_PATH);
  char vol[MAX_PATH] = {0};
  if (!GetVolumePathNameA(win, vol, MAX_PATH)) return -1;
  const std::string guid = volume_guid_for(vol);
  if (system_volume_guid) *system_volume_guid = guid;
  return guid.empty() ? -1 : volume_disk(guid);
}

// Partitions on a disk that could hold data (ignores unused entries and the
// Microsoft Reserved partition). Returns -1 if the layout can't be read.
int data_partitions(int disk, std::string* style = nullptr) {
  Handle h(open_query("PhysicalDrive" + std::to_string(disk)));
  if (!h.valid()) return -1;
  std::vector<BYTE> buf(sizeof(DRIVE_LAYOUT_INFORMATION_EX) + 128 * sizeof(PARTITION_INFORMATION_EX));
  DWORD n = 0;
  if (!DeviceIoControl(h.get(), IOCTL_DISK_GET_DRIVE_LAYOUT_EX, nullptr, 0, buf.data(),
                       static_cast<DWORD>(buf.size()), &n, nullptr))
    return -1;
  auto* L = reinterpret_cast<DRIVE_LAYOUT_INFORMATION_EX*>(buf.data());
  if (style) *style = L->PartitionStyle == PARTITION_STYLE_GPT ? "GPT" : L->PartitionStyle == PARTITION_STYLE_MBR ? "MBR" : "RAW";
  int count = 0;
  for (DWORD i = 0; i < L->PartitionCount; ++i) {
    const PARTITION_INFORMATION_EX& p = L->PartitionEntry[i];
    if (p.PartitionLength.QuadPart == 0) continue;
    if (p.PartitionStyle == PARTITION_STYLE_MBR && p.Mbr.PartitionType == PARTITION_ENTRY_UNUSED) continue;
    if (p.PartitionStyle == PARTITION_STYLE_GPT && IsEqualGUID(p.Gpt.PartitionType, kMsrGuid)) continue;
    ++count;
  }
  return count;
}

long long disk_size(int disk) {
  Handle h(open_query("PhysicalDrive" + std::to_string(disk)));
  if (!h.valid()) return -1;
  DISK_GEOMETRY_EX g{};
  DWORD n = 0;
  if (!DeviceIoControl(h.get(), IOCTL_DISK_GET_DRIVE_GEOMETRY_EX, nullptr, 0, &g, sizeof(g), &n, nullptr))
    return -1;
  return g.DiskSize.QuadPart;
}

// ---------------------------------------------------------------------------
int cmd_isadmin() {
  BOOL member = FALSE;
  SID_IDENTIFIER_AUTHORITY nt = SECURITY_NT_AUTHORITY;
  PSID admins = nullptr;
  if (AllocateAndInitializeSid(&nt, 2, SECURITY_BUILTIN_DOMAIN_RID, DOMAIN_ALIAS_RID_ADMINS, 0, 0, 0, 0, 0, 0,
                               &admins)) {
    CheckTokenMembership(nullptr, admins, &member);
    FreeSid(admins);
  }
  std::printf("%d\n", member ? 1 : 0);
  return 0;
}

int cmd_resolve(const std::string& path) {
  std::smatch m;
  static const std::regex drive_re(R"(PhysicalDrive(\d+)$)", std::regex::icase);
  std::string sys_guid;
  const int sys_disk = system_disk_number(&sys_guid);
  if (std::regex_search(path, m, drive_re)) {
    const int disk = std::stoi(m[1].str());
    std::string style;
    const int parts = data_partitions(disk, &style);
    std::printf("kind=device\ndisk=%d\ncounters=PhysicalDrive%d\nsize=%lld\npartitions=%d\npartition_style=%s\n"
                "system_disk=%d\n",
                disk, disk, disk_size(disk), parts, style.c_str(), disk == sys_disk ? 1 : 0);
    return 0;
  }
  char full[MAX_PATH] = {0}, vol[MAX_PATH] = {0};
  if (!GetFullPathNameA(path.c_str(), MAX_PATH, full, nullptr) || !GetVolumePathNameA(full, vol, MAX_PATH)) {
    std::fprintf(stderr, "cannot resolve volume of %s (error %lu)\n", path.c_str(), GetLastError());
    return 1;
  }
  const char* types[] = {"unknown", "invalid", "removable", "fixed", "remote", "cdrom", "ramdisk"};
  const UINT dt = GetDriveTypeA(vol);
  char fs[MAX_PATH] = {0};
  DWORD serial = 0, maxlen = 0, flags = 0;
  GetVolumeInformationA(vol, nullptr, 0, &serial, &maxlen, &flags, fs, MAX_PATH);
  ULARGE_INTEGER avail{}, total{}, freeb{};
  GetDiskFreeSpaceExA(vol, &avail, &total, &freeb);
  DWORD spc = 0, bps = 0, nfree = 0, ntotal = 0;
  GetDiskFreeSpaceA(vol, &spc, &bps, &nfree, &ntotal);
  const std::string guid = volume_guid_for(vol);
  int extents = 0;
  const int disk = guid.empty() ? -1 : volume_disk(guid, &extents);
  std::string counters = guid;
  while (!counters.empty() && counters.back() == '\\') counters.pop_back();
  std::printf("kind=file\nfull_path=%s\nvolume=%s\ncounters=%s\nfs=%s\ndrive_type=%s\nfree=%llu\n"
              "cluster_bytes=%lu\ndisk=%d\nextents=%d\nsystem_disk=%d\nsystem_volume=%d\n",
              full, vol, counters.c_str(), fs, dt < 7 ? types[dt] : "unknown",
              static_cast<unsigned long long>(avail.QuadPart), spc * bps, disk, extents,
              (disk >= 0 && disk == sys_disk) ? 1 : 0, (!guid.empty() && guid == sys_guid) ? 1 : 0);
  return 0;
}

int cmd_counters(const std::string& dev) {
  Handle h(open_query(dev));
  DISK_PERFORMANCE p{};
  DWORD n = 0;
  if (!h.valid() || !DeviceIoControl(h.get(), IOCTL_DISK_PERFORMANCE, nullptr, 0, &p, sizeof(p), &n, nullptr)) {
    std::printf("NA NA NA NA\n");
    return 0;
  }
  std::printf("%lu %lld %lu %lld\n", p.ReadCount, p.BytesRead.QuadPart, p.WriteCount, p.BytesWritten.QuadPart);
  return 0;
}

bool read_temperature(int disk, int* cur, int* warn, int* crit) {
  Handle h(open_query("PhysicalDrive" + std::to_string(disk)));
  std::vector<BYTE> buf;
  if (!h.valid() || !query_property(h.get(), kStorageDeviceTemperatureProperty, buf) ||
      buf.size() < sizeof(TemperatureDescriptor))
    return false;
  auto* d = reinterpret_cast<const TemperatureDescriptor*>(buf.data());
  if (d->InfoCount == 0) return false;
  *cur = d->Info[0].Temperature;  // degrees Celsius
  if (warn) *warn = d->WarningTemperature;
  if (crit) *crit = d->CriticalTemperature;
  return true;
}

int cmd_temp(int disk) {
  int t = 0;
  if (read_temperature(disk, &t, nullptr, nullptr)) std::printf("%d\n", t);
  else std::printf("NA\n");
  return 0;
}

int cmd_info(int disk) {
  Handle h(open_query("PhysicalDrive" + std::to_string(disk)));
  if (!h.valid()) {
    std::fprintf(stderr, "cannot open PhysicalDrive%d (error %lu)\n", disk, GetLastError());
    return 1;
  }
  std::string vendor, product, revision, bus = "?";
  std::vector<BYTE> buf;
  if (query_property(h.get(), StorageDeviceProperty, buf) && buf.size() >= sizeof(STORAGE_DEVICE_DESCRIPTOR)) {
    auto* d = reinterpret_cast<const STORAGE_DEVICE_DESCRIPTOR*>(buf.data());
    vendor = descriptor_string(buf, d->VendorIdOffset);
    product = descriptor_string(buf, d->ProductIdOffset);
    revision = descriptor_string(buf, d->ProductRevisionOffset);
    bus = bus_name(static_cast<int>(d->BusType));
  }
  int logical = -1, physical = -1;
  if (query_property(h.get(), kStorageAccessAlignmentProperty, buf) && buf.size() >= sizeof(AccessAlignment)) {
    auto* a = reinterpret_cast<const AccessAlignment*>(buf.data());
    logical = static_cast<int>(a->BytesPerLogicalSector);
    physical = static_cast<int>(a->BytesPerPhysicalSector);
  }
  std::string wc = "unknown";
  if (query_property(h.get(), kStorageDeviceWriteCacheProperty, buf) && buf.size() >= sizeof(WriteCacheProperty)) {
    auto* w = reinterpret_cast<const WriteCacheProperty*>(buf.data());
    wc = w->WriteCacheEnabled == 2 ? "enabled" : w->WriteCacheEnabled == 1 ? "disabled" : "unknown";
  }
  int trim_on = -1, seek = -1;
  if (query_property(h.get(), kStorageDeviceTrimProperty, buf) && buf.size() >= sizeof(TrimDescriptor))
    trim_on = reinterpret_cast<const TrimDescriptor*>(buf.data())->TrimEnabled ? 1 : 0;
  if (query_property(h.get(), kStorageDeviceSeekPenaltyProperty, buf) && buf.size() >= sizeof(SeekPenalty))
    seek = reinterpret_cast<const SeekPenalty*>(buf.data())->IncursSeekPenalty ? 1 : 0;
  int t = 0, tw = 0, tc = 0;
  const bool have_t = read_temperature(disk, &t, &tw, &tc);
  std::string style;
  const int parts = data_partitions(disk, &style);
  const int sys = system_disk_number();
  std::printf(
      "{\"disk\": %d, \"vendor\": \"%s\", \"model\": \"%s\", \"firmware\": \"%s\", \"bus\": \"%s\", "
      "\"size_bytes\": %lld, \"logical_sector\": %d, \"physical_sector\": %d, \"write_cache\": \"%s\", "
      "\"trim_enabled\": %d, \"seek_penalty\": %d, \"partition_style\": \"%s\", \"data_partitions\": %d, "
      "\"system_disk\": %s, \"temp_c\": %s, \"temp_warning_c\": %s, \"temp_critical_c\": %s}\n",
      disk, json_escape(vendor).c_str(), json_escape(product).c_str(), json_escape(revision).c_str(), bus.c_str(),
      disk_size(disk), logical, physical, wc.c_str(), trim_on, seek, style.c_str(), parts,
      disk == sys ? "true" : "false", have_t ? std::to_string(t).c_str() : "null",
      have_t ? std::to_string(tw).c_str() : "null", have_t ? std::to_string(tc).c_str() : "null");
  return 0;
}

int cmd_mkunwritten(const std::string& path, long long bytes) {
  // EOF is moved with SetEndOfFile, so NTFS allocates clusters but the file's
  // valid data length stays 0: reads return zeros without touching the disk,
  // and the first write at offset X makes NTFS zero-fill [VDL, X) first.
  Handle h(CreateFileA(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr));
  if (!h.valid()) {
    std::fprintf(stderr, "CreateFile %s failed (error %lu)\n", path.c_str(), GetLastError());
    return 1;
  }
  LARGE_INTEGER li;
  li.QuadPart = bytes;
  if (!SetFilePointerEx(h.get(), li, nullptr, FILE_BEGIN) || !SetEndOfFile(h.get())) {
    std::fprintf(stderr, "SetEndOfFile failed (error %lu)\n", GetLastError());
    return 1;
  }
  std::printf("created %s (%lld bytes, unwritten)\n", path.c_str(), bytes);
  return 0;
}

bool enable_privilege(const char* name) {
  HANDLE tok = nullptr;
  if (!OpenProcessToken(GetCurrentProcess(), TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY, &tok)) return false;
  TOKEN_PRIVILEGES tp{};
  tp.PrivilegeCount = 1;
  tp.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED;
  bool ok = LookupPrivilegeValueA(nullptr, name, &tp.Privileges[0].Luid) &&
            AdjustTokenPrivileges(tok, FALSE, &tp, sizeof(tp), nullptr, nullptr) &&
            GetLastError() == ERROR_SUCCESS;
  CloseHandle(tok);
  return ok;
}

int cmd_purge_standby() {
  // Same operations as Sysinternals RAMMap "Empty Standby List".
  using NtSetSystemInformationFn = LONG(WINAPI*)(INT, PVOID, ULONG);
  constexpr INT kSystemMemoryListInformation = 80;
  constexpr INT kMemoryFlushModifiedList = 3, kMemoryPurgeStandbyList = 4;
  if (!enable_privilege("SeProfileSingleProcessPrivilege") || !enable_privilege("SeIncreaseQuotaPrivilege")) {
    std::fprintf(stderr, "purge-standby needs an elevated shell (Run as administrator)\n");
    return 1;
  }
  SetSystemFileCacheSize(static_cast<SIZE_T>(-1), static_cast<SIZE_T>(-1), 0);  // trim cache working set
  auto fn = reinterpret_cast<NtSetSystemInformationFn>(
      reinterpret_cast<void*>(GetProcAddress(GetModuleHandleA("ntdll.dll"), "NtSetSystemInformation")));
  if (!fn) return 1;
  for (INT cmd : {kMemoryFlushModifiedList, kMemoryPurgeStandbyList}) {
    LONG st = fn(kSystemMemoryListInformation, &cmd, sizeof(cmd));
    if (st < 0) {
      std::fprintf(stderr, "NtSetSystemInformation(%d) failed: 0x%08lx\n", cmd, static_cast<unsigned long>(st));
      return 1;
    }
  }
  std::printf("purged\n");
  return 0;
}

int usage() {
  std::fprintf(stderr,
               "usage: winstat isadmin | resolve <path> | counters <device> | temp <disk#> | info <disk#> |\n"
               "               mkunwritten <path> <bytes> | purge-standby\n");
  return 2;
}

}  // namespace

int main(int argc, char** argv) {
  _setmode(_fileno(stdout), _O_BINARY);
  if (argc < 2) return usage();
  const std::string cmd = argv[1];
  try {
    if (cmd == "isadmin") return cmd_isadmin();
    if (cmd == "resolve" && argc == 3) return cmd_resolve(argv[2]);
    if (cmd == "counters" && argc == 3) return cmd_counters(argv[2]);
    if (cmd == "temp" && argc == 3) return cmd_temp(std::atoi(argv[2]));
    if (cmd == "info" && argc == 3) return cmd_info(std::atoi(argv[2]));
    if (cmd == "mkunwritten" && argc == 4) return cmd_mkunwritten(argv[2], std::atoll(argv[3]));
    if (cmd == "purge-standby") return cmd_purge_standby();
  } catch (const std::exception& e) {
    std::fprintf(stderr, "winstat: %s\n", e.what());
    return 1;
  }
  return usage();
}
