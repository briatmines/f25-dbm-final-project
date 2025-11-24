#!/bin/bash

# Usage: ./src/mk-csv.sh <json-directory> > <csv-file>
# ./src/mk-csv.sh ./mc-assets/data/minecraft/recipe/ > ./mc-data/recipes.csv
# ./src/mk-csv.sh ./mc-assets/data/minecraft/tags/item/ > ./mc-data/tags.csv

# cd to directory of json files
cd "$1"

# loop over json files
find . -name '*.json' -printf '%P\0' |
while IFS= read -r -d $'\0' file; do
    printf '"'
    printf 'minecraft:%s' "${file%.json}" | sed 's/"/""/g'
    printf '","'
    sed 's/"/""/g' < "./$file" | tr -d $'\r\n'
    printf $'"\r\n'
done
