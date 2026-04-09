#!/bin/bash
set -euo pipefail


if [ ! -d bdwgc/.git ]
then
    git clone https://github.com/ivmai/bdwgc.git
    cd bdwgc
else
    cd bdwgc
    git pull
fi

rm -rf build
mkdir -p m4

./autogen.sh

CFLAGS="-std=c99 -pedantic" ./configure --enable-static --disable-shared --prefix="$(pwd)/../runtime/numerobis/libs/bdwgc"

make
make install
