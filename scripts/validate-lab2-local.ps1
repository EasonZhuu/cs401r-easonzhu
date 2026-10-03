param(
  [string]$DockerExe = '',
  [string]$TerraformExe = 'terraform',
  [string]$AwsExe = 'aws'
)

$ErrorActionPreference = 'Stop'
$repoPath = Split-Path -Parent $PSScriptRoot
$localPath = Join-Path $repoPath 'infrastructure/environments/local'
$workPath = Join-Path (Split-Path -Parent $repoPath) '.tools/local-validation'
$reportPath = Join-Path $repoPath 'docs/lab2-localstack-output.txt'
$planPath = Join-Path $workPath 'lab2-local.tfplan'

if (-not $DockerExe) {
  $dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
  $DockerExe = if ($dockerCommand) { $dockerCommand.Source } else {
    Join-Path $env:LOCALAPPDATA 'Programs/DockerDesktop/resources/bin/docker.exe'
  }
}
if (-not (Test-Path -LiteralPath $DockerExe)) { throw 'Docker CLI not found' }
New-Item -ItemType Directory -Path $workPath -Force | Out-Null

$writer = [IO.StreamWriter]::new($reportPath, $false, [Text.UTF8Encoding]::new($false))
$writer.AutoFlush = $true
$envNames = @('AWS_ACCESS_KEY_ID','AWS_SECRET_ACCESS_KEY','AWS_SESSION_TOKEN','AWS_DEFAULT_REGION','AWS_EC2_METADATA_DISABLED','AWS_MAX_ATTEMPTS')
$savedEnvironment = @{}
foreach ($name in $envNames) { $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }

function Write-Evidence {
  param([string]$Message)
  $writer.WriteLine($Message)
  Write-Host $Message
}

function Invoke-Logged {
  param([string]$Title, [string]$Executable, [string[]]$Arguments)
  Write-Evidence ("`n== " + $Title + ' ==')
  $lines = & $Executable @Arguments 2>&1
  $exitCode = $LASTEXITCODE
  foreach ($line in $lines) { Write-Evidence ([string]$line) }
  if ($exitCode -ne 0) { throw ($Title + ' failed with exit code ' + $exitCode) }
  return ($lines -join [Environment]::NewLine)
}

function Invoke-LocalAws {
  param([string]$Title, [string[]]$Arguments)
  $argsWithEndpoint = @('--endpoint-url','http://localhost:4566','--region','us-east-1','--output','json','--no-cli-pager','--cli-connect-timeout','5','--cli-read-timeout','20') + $Arguments
  return (Invoke-Logged -Title $Title -Executable $AwsExe -Arguments $argsWithEndpoint | ConvertFrom-Json -Depth 50)
}

Push-Location $repoPath
try {
  $env:AWS_ACCESS_KEY_ID = 'test'
  $env:AWS_SECRET_ACCESS_KEY = 'test'
  $env:AWS_SESSION_TOKEN = ''
  $env:AWS_DEFAULT_REGION = 'us-east-1'
  $env:AWS_EC2_METADATA_DISABLED = 'true'
  $env:AWS_MAX_ATTEMPTS = '1'

  Write-Evidence '== NorthStar Lab 2 - LocalStack validation =='
  Write-Evidence ('date: ' + [DateTime]::UtcNow.ToString('o'))
  Write-Evidence 'Endpoint: http://localhost:4566; test credentials; no real AWS apply'
  Invoke-Logged 'docker compose up' $DockerExe @('compose','up','-d','--wait','--wait-timeout','120') | Out-Null
  Invoke-Logged 'terraform init' $TerraformExe @("-chdir=$localPath",'init','-input=false','-no-color') | Out-Null
  Invoke-Logged 'terraform validate' $TerraformExe @("-chdir=$localPath",'validate','-no-color') | Out-Null

  $identity = Invoke-LocalAws 'LocalStack sts get-caller-identity' @('sts','get-caller-identity')
  if ($identity.Account -ne '000000000000') { throw 'Unexpected local account; refusing to apply' }

  Invoke-Logged 'terraform plan' $TerraformExe @("-chdir=$localPath",'plan','-input=false','-no-color',"-out=$planPath") | Out-Null
  $planLines = & $TerraformExe "-chdir=$localPath" show -json $planPath
  if ($LASTEXITCODE -ne 0) { throw 'Could not inspect saved plan' }
  $plan = ($planLines -join [Environment]::NewLine) | ConvertFrom-Json -Depth 100
  $deletions = @($plan.resource_changes | Where-Object { $_.change.actions -contains 'delete' })
  if ($deletions.Count -gt 0) { throw 'Plan contains deletion or replacement; stopped before apply' }
  $unexpected = @($plan.resource_changes | Where-Object {
    $_.address -notmatch '^module\.(vpc|storage|iam)\.' -or
    $_.type -in @('aws_nat_gateway','aws_eip','aws_s3_bucket_lifecycle_configuration')
  })
  if ($unexpected.Count -gt 0) { throw 'Unexpected resources in local plan; stopped before apply' }

  Write-Evidence 'Plan guard passed: no deletion/replacement, NAT, lifecycle configuration, or SageMaker deployment'
  Invoke-Logged 'terraform apply saved local plan' $TerraformExe @("-chdir=$localPath",'apply','-input=false','-no-color',$planPath) | Out-Null
  $outputs = Invoke-Logged 'terraform output' $TerraformExe @("-chdir=$localPath",'output','-json') | ConvertFrom-Json -Depth 50
  $bucket = $outputs.s3_bucket_name.value
  Invoke-Logged 'LocalStack S3 prefix objects' $AwsExe @('--endpoint-url','http://localhost:4566','--region','us-east-1','--no-cli-pager','s3','ls',"s3://$bucket/",'--recursive') | Out-Null

  $roles = Invoke-LocalAws 'LocalStack IAM roles' @('iam','list-roles','--query','Roles[].RoleName')
  foreach ($role in @('MLEngineer','DataEngineer','ModelMonitor')) {
    $name = 'northstar-local-' + $role
    if ($name -notin $roles) { throw ('Missing role: ' + $name) }
    Invoke-LocalAws ("Trust policy: $name") @('iam','get-role','--role-name',$name,'--query','Role.AssumeRolePolicyDocument') | Out-Null
    $attachments = Invoke-LocalAws ("Policy attachment: $name") @('iam','list-attached-role-policies','--role-name',$name)
    if ($attachments.AttachedPolicies.Count -ne 1) { throw ('Unexpected policy attachment count: ' + $name) }
  }

  $vpcs = Invoke-LocalAws 'LocalStack VPCs' @('ec2','describe-vpcs')
  $vpc = @($vpcs.Vpcs | Where-Object VpcId -eq $outputs.vpc_id.value)
  if ($vpc.Count -ne 1 -or $vpc[0].CidrBlock -ne '10.0.0.0/16') { throw 'Project VPC missing or CIDR incorrect' }
  $subnetResponse = Invoke-LocalAws 'LocalStack subnets' @('ec2','describe-subnets','--filters',('Name=vpc-id,Values=' + $outputs.vpc_id.value))
  $public = @($subnetResponse.Subnets | Where-Object CidrBlock -eq '10.0.100.0/24')
  $private = @($subnetResponse.Subnets | Where-Object CidrBlock -eq '10.0.1.0/24')
  if ($public.Count -ne 1 -or $private.Count -ne 1 -or -not $public[0].MapPublicIpOnLaunch -or $private[0].MapPublicIpOnLaunch) {
    throw 'Public/private subnet configuration incorrect'
  }
  $nat = Invoke-LocalAws 'LocalStack NAT gateways (expected: none)' @('ec2','describe-nat-gateways','--filter',('Name=vpc-id,Values=' + $outputs.vpc_id.value))
  if ($nat.NatGateways.Count -ne 0) { throw 'NAT should be disabled locally' }
  Write-Evidence "`nRESULT: PASS - three IAM roles with policies; VPC; public/private subnets; NAT skipped"
  Write-Evidence 'LIMIT: LocalStack does not verify real SageMaker deployment, NAT, S3 lifecycle, or effective AWS IAM permissions'
} catch {
  Write-Evidence ('RESULT: FAIL - ' + $_.Exception.Message)
  throw
} finally {
  foreach ($name in $envNames) { [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process') }
  Pop-Location
  $writer.Dispose()
}
