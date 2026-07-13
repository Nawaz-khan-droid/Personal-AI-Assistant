$token = Get-Content "$PSScriptRoot\token.txt" -Raw
python deploy.py $token
