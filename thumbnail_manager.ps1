<#
.SYNOPSIS
    A script to automate the creation and fixing of thumbnails for video files.
.DESCRIPTION
    This script scans a directory and its subdirectories for video files and ensures that each video has a corresponding thumbnail and a set of "edit mode" thumbnails.
    It checks for missing thumbnails, incorrect resolutions, and creates/replaces them as needed.
.NOTES
    Author: Jules
    Version: 1.3
#>

param (
    [string]$LaunchDir = (Get-Location).Path
)

# --- CONFIGURATION ---
$NormalThumbnailWidth = 320
$EditThumbnailWidth = 256
$FfmpegQualityArgs = @('-q:v', '6') # Changed to an array for safer execution
$NumberOfEditThumbnails = 10
$VideoExtensions = @('.mp4', '.avi', '.mov', '.mkv', '.wmv', 'flv')
$SpecialFolders = @('Landscape', 'Landscape Rotate', 'Edit')
$MaxParallelJobs = [System.Environment]::ProcessorCount

# --- SCRIPT BODY ---

function Get-VideoFiles {
    param (
        [string]$Path
    )
    return Get-ChildItem -Path $Path -Recurse -File | Where-Object { $_.Extension -in $VideoExtensions }
}

function Get-ImageResolution {
    param (
        [string]$ImagePath
    )
    try {
        Add-Type -AssemblyName System.Drawing
        $img = [System.Drawing.Image]::FromFile($ImagePath)
        $width = $img.Width
        $img.Dispose()
        return $width
    }
    catch {
        Write-Warning "Could not read resolution for: $ImagePath"
        return 0
    }
}

function Get-VideoDuration {
    param (
        [string]$VideoPath
    )
    try {
        $durationString = ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 -i $VideoPath
        return [math]::Floor([double]$durationString)
    }
    catch {
        Write-Warning "Could not get duration for: $VideoPath"
        return 0
    }
}


Write-Host "Starting thumbnail analysis in: $LaunchDir"
Write-Host "------------------------------------------"

# --- ANALYSIS PHASE ---
Write-Host "Phase 1: Analyzing directory structure and files..."

# Initialize lists to hold required actions
$missingThumbnailFolders = [System.Collections.Generic.List[string]]::new()
$missingEditThumbnailFolders = [System.Collections.Generic.List[string]]::new()
$missingNormalThumbnails = [System.Collections.Generic.List[string]]::new()
$incorrectNormalThumbnails = [System.Collections.Generic.List[string]]::new()
$missingEditThumbnails = [System.Collections.Generic.List[PSObject]]::new()
$incorrectEditThumbnails = [System.Collections.Generic.List[PSObject]]::new()


# Get all video files recursively in one go
$allVideoFiles = Get-VideoFiles -Path $LaunchDir

# Use HashSets to track which folders we've already checked for existence
$checkedThumbnailFolders = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
$checkedEditThumbnailFolders = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

foreach ($video in $allVideoFiles) {
    $baseName = $video.BaseName

    # --- Determine the correct base directory for thumbnails ---
    $parentDir = $video.Directory
    $baseDir = $parentDir
    if ($SpecialFolders -contains $parentDir.Name) {
        $baseDir = $parentDir.Parent
    }

    $thumbnailDir = Join-Path -Path $baseDir.FullName -ChildPath "Thumbnails"
    $editThumbnailDir = Join-Path -Path $baseDir.FullName -ChildPath "Edit Thumbnails"

    # --- Check for missing thumbnail folders (only once per folder) ---
    if ($checkedThumbnailFolders.Add($thumbnailDir)) {
        if (-not (Test-Path $thumbnailDir)) {
            $missingThumbnailFolders.Add($thumbnailDir)
        }
    }
    if ($checkedEditThumbnailFolders.Add($editThumbnailDir)) {
         if (-not (Test-Path $editThumbnailDir)) {
            $missingEditThumbnailFolders.Add($editThumbnailDir)
        }
    }

    # Analyze each video file
    $normalThumbnailPath = Join-Path -Path $thumbnailDir -ChildPath "$baseName.jpg"

    # --- Normal Thumbnail Check ---
    if (Test-Path $normalThumbnailPath) {
        $width = Get-ImageResolution -ImagePath $normalThumbnailPath
        if ($width -ne 0 -and $width -ne $NormalThumbnailWidth) {
            $incorrectNormalThumbnails.Add($normalThumbnailPath)
        }
    }
    else {
        $missingNormalThumbnails.Add($video.FullName)
    }

    # --- Edit Mode Thumbnail Check ---
    $duration = Get-VideoDuration -VideoPath $video.FullName
    $expectedThumbCount = [math]::Min($NumberOfEditThumbnails, [math]::Floor($duration / 2)) # Ensure at least 2s per thumb

    $existingEditThumbnails = Get-ChildItem -Path $editThumbnailDir -Filter "$baseName*.jpg" -ErrorAction SilentlyContinue

    if ($existingEditThumbnails.Count -lt $expectedThumbCount) {
         $missingEditThumbnails.Add(@{ Video = $video; Expected = $expectedThumbCount; Found = $existingEditThumbnails.Count })
    } else {
        $firstEditThumb = $existingEditThumbnails | Sort-Object Name | Select-Object -First 1
        $width = Get-ImageResolution -ImagePath $firstEditThumb.FullName
        if ($width -ne 0 -and $width -ne $EditThumbnailWidth) {
            $incorrectEditThumbnails.Add(@{ Video = $video; Thumbnails = $existingEditThumbnails })
        }
    }
}


# --- SUMMARY PHASE ---
Write-Host ""
Write-Host "--- Analysis Complete ---" -ForegroundColor Green
Write-Host "Phase 2: Summary of required actions..."

Write-Host ""
Write-Host "Directory Fixes:"
Write-Host " - Missing 'Thumbnails' folders to create: $($missingThumbnailFolders.Count)"
Write-Host " - Missing 'Edit Thumbnails' folders to create: $($missingEditThumbnailFolders.Count)"
Write-Host ""
Write-Host "Normal Thumbnail Fixes:"
Write-Host " - Videos missing a normal thumbnail: $($missingNormalThumbnails.Count)"
Write-Host " - Existing thumbnails with incorrect resolution: $($incorrectNormalThumbnails.Count)"
Write-Host ""
Write-Host "Edit Mode Thumbnail Fixes:"
Write-Host " - Videos with missing edit thumbnails: $($missingEditThumbnails.Count)"
Write-Host " - Videos with incorrect resolution edit thumbnails: $($incorrectEditThumbnails.Count)"
Write-Host ""

$totalActions = $missingThumbnailFolders.Count + $missingEditThumbnailFolders.Count + $missingNormalThumbnails.Count + $incorrectNormalThumbnails.Count + $missingEditThumbnails.Count + $incorrectEditThumbnails.Count

if ($totalActions -eq 0) {
    Write-Host "No actions required. All thumbnails are correct." -ForegroundColor Green
    exit
}

$response = Read-Host "Proceed with applying these fixes? (y/n)"
if ($response -ne 'y') {
    Write-Host "Operation cancelled by user."
    exit
}


# --- PROCESSING PHASE ---
Write-Host ""
Write-Host "--- Starting Processing ---" -ForegroundColor Green
Write-Host "Phase 3: Starting thumbnail generation and fixing..."
Write-Host ""

# 1. Create missing directories
if ($missingThumbnailFolders.Count -gt 0) {
    Write-Host "Creating $($missingThumbnailFolders.Count) missing 'Thumbnails' directories..."
    $missingThumbnailFolders | ForEach-Object {
        Write-Host " - Creating $_"
        New-Item -Path $_ -ItemType Directory -Force | Out-Null
    }
}
if ($missingEditThumbnailFolders.Count -gt 0) {
    Write-Host "Creating $($missingEditThumbnailFolders.Count) missing 'Edit Thumbnails' directories..."
    $missingEditThumbnailFolders | ForEach-Object {
        Write-Host " - Creating $_"
        New-Item -Path $_ -ItemType Directory -Force | Out-Null
    }
}


# 2. Process Normal Thumbnails
$videosForNormalThumbnailing = [System.Collections.Generic.List[string]]::new()
$videosForNormalThumbnailing.AddRange($missingNormalThumbnails)
$incorrectNormalThumbnails | ForEach-Object {
    $videoName = [System.IO.Path]::GetFileNameWithoutExtension($_)
    $parentDir = (Get-Item -LiteralPath $_).Directory.Parent
    $videoFile = Get-VideoFiles -Path $parentDir.FullName | Where-Object { $_.BaseName -eq $videoName } | Select-Object -First 1
    if ($videoFile) {
        $videosForNormalThumbnailing.Add($videoFile.FullName)
    }
    Remove-Item -Path $_ -Force
}

if ($videosForNormalThumbnailing.Count -gt 0) {
    Write-Host ""
    Write-Host "Generating/Replacing $($videosForNormalThumbnailing.Count) normal thumbnails (in parallel)..."

    # Create a synchronized list to hold messages from parallel threads
    $syncMessages = [System.Collections.Concurrent.ConcurrentBag[string]]::new()

    $videosForNormalThumbnailing | ForEach-Object -Parallel {
        $videoPath = $_
        $video = Get-Item -LiteralPath $videoPath
        $baseName = $video.BaseName

        $parentDir = $video.Directory
        $baseDir = $parentDir
        if ($using:SpecialFolders -contains $parentDir.Name) {
            $baseDir = $parentDir.Parent
        }

        $thumbnailDir = Join-Path -Path $baseDir.FullName -ChildPath "Thumbnails"
        $outputPath = Join-Path -Path $thumbnailDir -ChildPath "$baseName.jpg"

        $localSyncMessages = $using:syncMessages
        $localSyncMessages.Add(" - Creating normal thumbnail for: $baseName")

        $ffmpegArgs = @(
            '-y', '-hide_banner', '-loglevel', 'error',
            '-i', $videoPath,
            '-ss', '00:00:02.000',
            '-frames:v', '1',
            '-vf', "scale=$(${using:NormalThumbnailWidth}):-1"
        )
        $ffmpegArgs += $using:FfmpegQualityArgs
        $ffmpegArgs += $outputPath

        & ffmpeg @ffmpegArgs

    } -ThrottleLimit $MaxParallelJobs

    # Print messages after parallel operation is complete
    $syncMessages | ForEach-Object { Write-Host $_ }
}


# 3. Process Edit Mode Thumbnails
$videosForEditThumbnailing = [System.Collections.Generic.List[PSObject]]::new()
$videosForEditThumbnailing.AddRange($missingEditThumbnails)
$videosForEditThumbnailing.AddRange($incorrectEditThumbnails)

$uniqueVideosForEdit = $videosForEditThumbnailing | Sort-Object -Property {$_.Video.FullName} -Unique

if ($uniqueVideosForEdit.Count -gt 0) {
    Write-Host ""
    Write-Host "Generating/Replacing edit mode thumbnails for $($uniqueVideosForEdit.Count) videos..."
    $editCounter = 0
    foreach ($item in $uniqueVideosForEdit) {
        $editCounter++
        $video = $item.Video
        $baseName = $video.BaseName

        $parentDir = $video.Directory
        $baseDir = $parentDir
        if ($SpecialFolders -contains $parentDir.Name) {
            $baseDir = $parentDir.Parent
        }
        $editThumbnailDir = Join-Path -Path $baseDir.FullName -ChildPath "Edit Thumbnails"

        Get-ChildItem -Path $editThumbnailDir -Filter "$baseName*.jpg" -ErrorAction SilentlyContinue | Remove-Item -Force

        Write-Host "[$editCounter of $($uniqueVideosForEdit.Count)] Processing edit thumbnails for: $baseName"

        $duration = Get-VideoDuration -VideoPath $video.FullName
        if ($duration -le 2) {
            Write-Warning "Video '$baseName' is too short for edit thumbnails."
            continue
        }

        $thumbCount = [math]::Min($NumberOfEditThumbnails, [math]::Floor($duration / 2))
        $interval = [math]::Floor($duration / $thumbCount)
        if ($interval -lt 1) { $interval = 1 }

        $outputPathPattern = Join-Path -Path $editThumbnailDir -ChildPath "${baseName}_%d.jpg"

        $ffmpegArgs = @(
            '-hide_banner', '-loglevel', 'error',
            '-i', $video.FullName,
            '-vf', "fps=1/$interval,scale=${EditThumbnailWidth}:-1",
            '-vframes', $thumbCount
        )
        $ffmpegArgs += $FfmpegQualityArgs
        $ffmpegArgs += $outputPathPattern

        & ffmpeg @ffmpegArgs
    }
}


Write-Host ""
Write-Host "------------------------------------------"
Write-Host "Script finished." -ForegroundColor Green
