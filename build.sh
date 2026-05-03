# Build script for LibreOffice Translator extension

#!/bin/bash

# Clean previous build
rm -f Translator.oxt
rm -rf __pycache__

# Build the extension
zip -r Translator.oxt . -x "*.git*" -x "*.oxt" -x "__pycache__/*" -x "README.md" -x "LICENSE" -x "build.sh" -x ".gitignore"

echo "Extension built: Translator.oxt"
