#!/bin/bash

# Usage: ./src/mk-recipes-csv.sh ./mc-assets/data/minecraft/recipe/ > ./mc-data/recipes.csv

cd "$1"

for file in *.json; do
    printf '"'
    sed 's/"/""/g' < "$file" | tr -d $'\r\n'
    printf $'"\r\n'
done
