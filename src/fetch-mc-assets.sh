#!/bin/bash

# Usage: ./src/fetch-mc-assets.sh <recent installed minecraft version> ./mc-assets

mkdir -p $2
cp "$HOME/.minecraft/versions/$1/$1.jar" "$2/$1.jar"
unzip "$2/$1.jar" -d "$2"
