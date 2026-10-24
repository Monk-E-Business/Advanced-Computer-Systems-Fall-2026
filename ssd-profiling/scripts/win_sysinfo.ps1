# win_sysinfo.ps1 - Windows facts for the SSD profiling run, printed as JSON.
# Called by scripts/collect_sysinfo.sh. Some fields (reliability counters,
# Defender exclusions) are only readable from an elevated shell; they come
# back empty otherwise.
$ErrorActionPreference = 'SilentlyContinue'

$os  = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$cs  = Get-CimInstance Win32_ComputerSystem

# Each disk with its PCIe link (read from the disk's parent controller, which
# for NVMe is the PCI device itself). Link speed codes: 1=2.5, 2=5, 3=8,
# 4=16, 5=32 GT/s.
$disks = foreach ($d in Get-CimInstance Win32_DiskDrive) {
  $parent = (Get-PnpDeviceProperty -InstanceId $d.PNPDeviceID -KeyName 'DEVPKEY_Device_Parent').Data
  $link = [ordered]@{}
  if ($parent) {
    Get-PnpDeviceProperty -InstanceId $parent |
      Where-Object { $_.KeyName -match 'PciDevice_(Current|Max)Link(Speed|Width)$' } |
      ForEach-Object { $link[($_.KeyName -replace '^DEVPKEY_PciDevice_', '')] = $_.Data }
  }
  [ordered]@{
    index = $d.Index; model = $d.Model; firmware = $d.FirmwareRevision
    interface = $d.InterfaceType; size = $d.Size; parent = $parent; link = $link
  }
}

$phys = Get-PhysicalDisk | Select-Object DeviceId, FriendlyName, BusType, MediaType, FirmwareVersion, Size, HealthStatus
$rel  = Get-PhysicalDisk | Get-StorageReliabilityCounter |
          Select-Object DeviceId, Temperature, TemperatureMax, Wear, PowerOnHours, ReadErrorsTotal, WriteErrorsTotal

[ordered]@{
  os                  = "$($os.Caption) $($os.Version) (build $($os.BuildNumber))"
  cpu_name            = $cpu.Name
  cpu_cores           = $cpu.NumberOfCores
  cpu_logical         = $cpu.NumberOfLogicalProcessors
  cpu_current_mhz     = $cpu.CurrentClockSpeed
  cpu_max_mhz         = $cpu.MaxClockSpeed
  ram_bytes           = $cs.TotalPhysicalMemory
  disks               = @($disks)
  physical_disks      = @($phys)
  reliability         = @($rel)
  defender_exclusions = @((Get-MpPreference).ExclusionPath)
} | ConvertTo-Json -Depth 6
