#!/bin/bash
# Copy one submission field to the clipboard.  usage:  ./submission/copy.sh 2
cd "$(dirname "$0")"
case "$1" in
  1) pbcopy < 1-oneliner.txt;      echo "✅ one-liner copied" ;;
  2) pbcopy < 2-description.txt;   echo "✅ 200-word description copied" ;;
  3) pbcopy < 3-video-comment.txt; echo "✅ video comment copied" ;;
  4) pbcopy < 4-fields.txt;        echo "✅ field list copied" ;;
  *) echo "usage: ./submission/copy.sh [1|2|3|4]"
     echo "  1  one-liner"; echo "  2  200-word description"
     echo "  3  video comment"; echo "  4  fields" ;;
esac
