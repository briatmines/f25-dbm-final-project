#!/bin/bash

# Usage: ./src/mk-csv.sh <json-directory> > <csv-file>
# ./src/mk-csv.sh ./mc-assets/data/minecraft/recipe/ > ./mc-data/recipes.csv
# ./src/mk-csv.sh ./mc-assets/data/minecraft/tags/item/ > ./mc-data/tags.csv

cd "$1"

for file in *.json; do
    printf "${file%.json}"
    printf ","
    printf '"'
    sed 's/"/""/g' < "$file" | tr -d $'\r\n'
    printf $'"\r\n'
done
