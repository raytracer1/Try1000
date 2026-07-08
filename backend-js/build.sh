#!/bin/bash
# Build the deployment package for FC Node.js
set -e
rm -rf package && mkdir package
cp -r src seed.js package/
cd package && npm init -y > /dev/null && npm i express cors cookie-parser jsonwebtoken google-auth-library pg drizzle-orm drizzle-kit --omit=dev 2>&1 | tail -1
echo "Build complete: $(du -sh . | cut -f1)"
