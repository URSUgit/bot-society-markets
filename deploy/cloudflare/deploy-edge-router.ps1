param(
    [string]$ConfigPath = "wrangler.jsonc"
)

npx wrangler@latest deploy --config $ConfigPath
