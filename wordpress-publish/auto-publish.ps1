# Auto-publish P2 + P3 to todosabordocr.com once firewall allows access.
# Usage (after unblock + with Application Password or basic auth):
#   .\auto-publish.ps1 -User "usuario" -AppPassword "xxxx xxxx xxxx xxxx"
param(
  [Parameter(Mandatory = $true)][string]$User,
  [Parameter(Mandatory = $true)][string]$AppPassword,
  [string]$BaseUrl = "http://todosabordocr.com"
)

$ErrorActionPreference = "Stop"
$pair = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes("${User}:${AppPassword}"))
$headers = @{
  Authorization = "Basic $pair"
  "Content-Type" = "application/json"
}
$ua = "Mozilla/5.0 TodosABordoPublisher/1.0"

function Test-Wp {
  $code = curl.exe -s -A $ua -o NUL -w "%{http_code}" --connect-timeout 10 -m 15 "$BaseUrl/wp-json/"
  return $code -eq "200"
}

if (-not (Test-Wp)) {
  Write-Error "WordPress API still blocked/unreachable at $BaseUrl/wp-json/"
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$p2Html = Get-Content (Join-Path $root "un-regalo-para-tu-peque\index.html") -Raw -Encoding UTF8
$p2Gracias = Get-Content (Join-Path $root "un-regalo-para-tu-peque\gracias.html") -Raw -Encoding UTF8
$p3Html = Get-Content (Join-Path $root "el-poder-de-ser-yo\index.html") -Raw -Encoding UTF8

function Upsert-Page($slug, $title, $content) {
  $search = curl.exe -s -A $ua -H "Authorization: Basic $pair" "$BaseUrl/wp-json/wp/v2/pages?slug=$slug&_fields=id,link"
  $existing = $search | ConvertFrom-Json
  $bodyObj = @{
    title   = $title
    slug    = $slug
    status  = "publish"
    content = $content
  }
  $body = $bodyObj | ConvertTo-Json -Depth 5
  $tmp = Join-Path $env:TEMP ("wp-page-" + $slug + ".json")
  [System.IO.File]::WriteAllText($tmp, $body, [System.Text.UTF8Encoding]::new($false))

  if ($existing -and $existing.Count -gt 0) {
    $id = $existing[0].id
    Write-Output "Updating page $slug id=$id"
    curl.exe -s -A $ua -X POST -H "Authorization: Basic $pair" -H "Content-Type: application/json" --data-binary "@$tmp" "$BaseUrl/wp-json/wp/v2/pages/$id"
  } else {
    Write-Output "Creating page $slug"
    curl.exe -s -A $ua -X POST -H "Authorization: Basic $pair" -H "Content-Type: application/json" --data-binary "@$tmp" "$BaseUrl/wp-json/wp/v2/pages"
  }
  Write-Output ""
}

# Embed P2 as custom HTML page content (works without Elementor plugin activate)
$p2Content = @"
<!-- wp:html -->
$p2Html
<!-- /wp:html -->
"@
$graciasContent = @"
<!-- wp:html -->
$p2Gracias
<!-- /wp:html -->
"@

Upsert-Page "un-regalo-para-tu-peque" "Un regalo para tu peque!" $p2Content
Upsert-Page "gracias-descarga-guia" "Gracias - Descarga guia" $graciasContent

Write-Output "NOTE: Proyecto 3 is a full static site with images/PHP. Upload el-poder-de-ser-yo.zip via File Manager OR WP plugin media."
Write-Output "P2 pages published. Public URLs:"
Write-Output "$BaseUrl/un-regalo-para-tu-peque/"
Write-Output "$BaseUrl/gracias-descarga-guia/"
