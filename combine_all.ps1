# Run from the project root: .\combine_all.ps1
# Combines data\wiki\*.md and data\*.csv into the consolidated knowledge-base files.

$root = $PSScriptRoot

$wikiDir = Join-Path $root "data\wiki"
$dataDir = Join-Path $root "data"
$wikiOut = Join-Path $root "dark_souls_3_wiki.md"
$csvOut  = Join-Path $root "dark_souls_3_csv.txt"

# Wiki

$wikiFiles = Get-ChildItem -Path $wikiDir -Filter "*.md" | Sort-Object Name

$buf = [System.Text.StringBuilder]::new(64MB)

$null = $buf.AppendLine("# Dark Souls 3 - Wiki Knowledge Base")
$null = $buf.AppendLine()
$null = $buf.AppendLine("> **CONTEXT FOR AI:** Every article in this file belongs exclusively to **Dark Souls 3**.")
$null = $buf.AppendLine("> Items that share names across Dark Souls titles (e.g. Moonlight Greatsword, Estus Flask,")
$null = $buf.AppendLine("> Pyromancy Flame) refer here ONLY to their Dark Souls 3 version,")
$null = $buf.AppendLine("> with stats, scaling, lore, and mechanics specific to that game.")
$null = $buf.AppendLine("> Do NOT mix this data with other Dark Souls entries.")
$null = $buf.AppendLine()
$null = $buf.AppendLine("---")
$null = $buf.AppendLine()

foreach ($file in $wikiFiles) {
    $title   = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
    $content = [System.IO.File]::ReadAllText($file.FullName, [System.Text.Encoding]::UTF8)

    $null = $buf.AppendLine("# [DS3] $title")
    $null = $buf.AppendLine()
    $null = $buf.Append($content)
    if (-not $content.EndsWith("`n")) { $null = $buf.AppendLine() }
    $null = $buf.AppendLine()
    $null = $buf.AppendLine("---")
    $null = $buf.AppendLine()
}

[System.IO.File]::WriteAllText($wikiOut, $buf.ToString(), [System.Text.Encoding]::UTF8)
Write-Host "Wiki done : $wikiOut  ($($wikiFiles.Count) articles)"

# CSV

$csvFiles = Get-ChildItem -Path $dataDir -Filter "*.csv" | Sort-Object Name

$buf = [System.Text.StringBuilder]::new(4MB)

$null = $buf.AppendLine("# Dark Souls 3 - CSV Data Tables")
$null = $buf.AppendLine()
$null = $buf.AppendLine("> **CONTEXT FOR AI:** All tables in this file are exclusively about **Dark Souls 3**.")
$null = $buf.AppendLine()
$null = $buf.AppendLine("---")
$null = $buf.AppendLine()

foreach ($file in $csvFiles) {
    $name    = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
    $content = [System.IO.File]::ReadAllText($file.FullName, [System.Text.Encoding]::UTF8)

    $null = $buf.AppendLine("== [DS3] $name ==")
    $null = $buf.AppendLine()
    $null = $buf.Append($content)
    if (-not $content.EndsWith("`n")) { $null = $buf.AppendLine() }
    $null = $buf.AppendLine()
    $null = $buf.AppendLine()
}

[System.IO.File]::WriteAllText($csvOut, $buf.ToString(), [System.Text.Encoding]::UTF8)
Write-Host "CSV  done : $csvOut  ($($csvFiles.Count) tables)"

Write-Host ""
Write-Host "All files generated."
