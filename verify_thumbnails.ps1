# Load the System.Drawing assembly to inspect image properties
[System.Reflection.Assembly]::LoadWithPartialName("System.Drawing") | Out-Null

# Get the directory where the script is located to use as the starting point for the scan.
$PSScriptRoot = Split-Path -Parent -Path $MyInvocation.MyCommand.Definition
Write-Host "Scanning for thumbnails starting from: $PSScriptRoot"

# Define the names of the thumbnail directories to search for.
$thumbnailFolderNames = @("Thumbnails", "Edit Thumbnails")

# Find all thumbnail directories recursively.
$thumbnailFolders = Get-ChildItem -Path $PSScriptRoot -Recurse -Directory | Where-Object { $_.Name -in $thumbnailFolderNames }

$incorrectThumbnails = [System.Collections.Generic.List[string]]::new()

Write-Host "Found $($thumbnailFolders.Count) thumbnail directories. Checking images..."

# Iterate through each found thumbnail directory.
foreach ($folder in $thumbnailFolders) {
    # Get all JPG files in the current directory.
    $images = Get-ChildItem -Path $folder.FullName -Filter *.jpg

    foreach ($imageFile in $images) {
        try {
            # Load the image to check its dimensions.
            $image = [System.Drawing.Image]::FromFile($imageFile.FullName)

            # A thumbnail is incorrect if its largest dimension is not 256px.
            $maxWidth = [Math]::Max($image.Width, $image.Height)

            if ($maxWidth -ne 256) {
                $incorrectThumbnails.Add($imageFile.FullName)
            }
        }
        catch {
            Write-Warning "Could not process file: $($imageFile.FullName). Error: $_"
        }
        finally {
            # Ensure the image object is disposed to release the file lock.
            if ($image) {
                $image.Dispose()
            }
        }
    }
}

# --- Reporting and User Confirmation ---
if ($incorrectThumbnails.Count -eq 0) {
    Write-Host "Scan Complete. All thumbnails are correctly sized." -ForegroundColor Green
    exit
}

Write-Host ""
Write-Host "Scan Complete. Found $($incorrectThumbnails.Count) incorrectly sized thumbnails." -ForegroundColor Yellow
$choice = Read-Host "Do you want to regenerate these thumbnails? (y/n)"

if ($choice -ne 'y' -and $choice -ne 'yes') {
    Write-Host "Operation cancelled by user."
    exit
}

Write-Host "Proceeding with regeneration..."

# Group incorrect edit thumbnails by their base video name.
$editThumbnailsToRegenerate = $incorrectThumbnails | Where-Object { $_ -like '*Edit Thumbnails*' } | ForEach-Object {
    $baseName = (Split-Path $_ -Leaf) -replace '_\d+\.jpg$', ''
    [PSCustomObject]@{
        BaseName = $baseName
        FullPath = $_
        VideoPath = (Get-ParentDirectoryMatchingVideo -Path $_ -BaseName $baseName)
    }
} | Group-Object -Property VideoPath

# Group normal thumbnails.
$normalThumbnailsToRegenerate = $incorrectThumbnails | Where-Object { $_ -like '*Thumbnails*' -and $_ -notlike '*Edit Thumbnails*' } | ForEach-Object {
    $baseName = (Split-Path $_ -Leaf) -replace '\.jpg$', ''
    [PSCustomObject]@{
        FullPath = $_
        VideoPath = (Get-ParentDirectoryMatchingVideo -Path $_ -BaseName $baseName)
    }
}

# Helper function to find the video file in parent directories.
function Get-ParentDirectoryMatchingVideo {
    param(
        [string]$Path,
        [string]$BaseName
    )
    $currentPath = Split-Path $Path -Parent
    while ($currentPath -ne $null -and $currentPath -ne "") {
        $videoFiles = Get-ChildItem -Path $currentPath -File | Where-Object { $_.BaseName -eq $BaseName -and $_.Extension -in ".mp4", ".avi", ".mov", ".mkv" }
        if ($videoFiles.Count -gt 0) {
            return $videoFiles[0].FullName
        }
        $currentPath = Split-Path $currentPath -Parent
    }
    return $null
}


# --- Regeneration ---
Write-Host "Regenerating normal thumbnails..."
$normalThumbnailsToRegenerate | ForEach-Object -Parallel {
    param($ThrottleLimit = 8)

    $thumb = $_
    if ($thumb.VideoPath) {
        Write-Host "Fixing $($thumb.FullPath)..."
        $ffmpegCommand = "ffmpeg -y -i ""$($thumb.VideoPath)"" -ss 00:00:02.000 -frames:v 1 -vf ""scale=256:256:force_original_aspect_ratio=decrease"" ""$($thumb.FullPath)"" -hide_banner -loglevel error"
        Invoke-Expression $ffmpegCommand
    } else {
        Write-Warning "Could not find matching video for $($thumb.FullPath)"
    }
}

Write-Host "Regenerating edit mode thumbnail sets..."
$editThumbnailsToRegenerate | ForEach-Object -Parallel {
    param($ThrottleLimit = 4) # Lower throttle for multi-frame extraction

    $group = $_
    $videoPath = $group.Name
    if ($videoPath) {
        $baseVideoName = Split-Path $videoPath -Leaf | ForEach-Object { $_.Substring(0, $_.LastIndexOf('.')) }
        $editThumbnailsPath = Join-Path (Split-Path (Split-Path $videoPath -Parent) -Parent) "Edit Thumbnails"
        Write-Host "Fixing set for $($baseVideoName)..."

        $durationStr = $(ffmpeg -i "$videoPath" 2>&1 | findstr "Duration")
        if ($durationStr -match '(\d{2}):(\d{2}):(\d{2})\.(\d{2})') {
            $duration = [int]$matches[1]*3600 + [int]$matches[2]*60 + [int]$matches[3]
        } else {
            $duration = 10 # Default duration if detection fails
        }

        $interval = [Math]::Max(1, [int]($duration / 10))

        for ($i = 1; $i -le 10; $i++) {
            $timestamp = ($i - 1) * $interval
            $outputPath = Join-Path $editThumbnailsPath "$($baseVideoName)_$i.jpg"
            $ffmpegCommand = "ffmpeg -y -ss $timestamp -i ""$videoPath"" -vframes 1 -vf ""scale=256:256:force_original_aspect_ratio=decrease"" ""$outputPath"" -hide_banner -loglevel error"
            Invoke-Expression $ffmpegCommand
        }
    } else {
        Write-Warning "Could not find matching video for set starting with $($group.Group[0].BaseName)"
    }
}

Write-Host ""
Write-Host "Regeneration complete." -ForegroundColor Green
