#!/bin/bash

# Usage: ./src/mk-recipies-csv.sh ./mc-assets/data/minecraft/recipie/ > ./mc-data/recipies.csv

cd "$1"

for file in *.json; do
    printf '"'
    sed 's/"/""/g' < "$file" | tr -d $'\r\n'
    printf $'"\r\n'
done
