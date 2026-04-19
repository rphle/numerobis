$originalDir = Get-Location

try {
    if (-not (Test-Path "bdwgc\.git")) {
        git clone https://github.com/ivmai/bdwgc.git
    }

    Set-Location bdwgc
    git pull

    if (Test-Path "build") { Remove-Item -Recurse -Force build }
    New-Item -ItemType Directory -Force build
    Set-Location build

    cmake .. `
        -G "Ninja" `
        -DCMAKE_C_STANDARD=11 `
        -DBUILD_SHARED_LIBS=OFF `
        -DGC_BUILD_SHARED_LIBS=OFF `
        -DCMAKE_INSTALL_PREFIX="../../runtime/numerobis/libs/bdwgc"

    cmake --build . --config Release
    cmake --install .
}
finally {
    Set-Location $originalDir
}
