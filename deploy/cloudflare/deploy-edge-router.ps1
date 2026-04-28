param(
    [string]$ConfigPath = "deploy/cloudflare/edge-router/wrangler.jsonc"
)

npx wrangler@latest deploy --config $ConfigPath
