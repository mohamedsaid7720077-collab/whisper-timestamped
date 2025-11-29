name: Build whisper.cpp Android (multi-ABI)

on:
  push:
    branches: [ main ]
  workflow_dispatch:

env:
  ANDROID_API_LEVEL: "26"
  NDK_VERSION: "25.2.9519653"
  CMAKE_VERSION: "3.22.1"
  CMDLINE_TOOLS_ZIP_URL: "https://dl.google.com/android/repository/commandlinetools-linux-9477386_latest.zip"

jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        abi: [ "arm64-v8a", "armeabi-v7a", "x86", "x86_64" ]

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set environment variables
        run: |
          echo "ANDROID_SDK_ROOT=$RUNNER_TEMP/android-sdk" >> $GITHUB_ENV
          echo "ANDROID_NDK_HOME=$RUNNER_TEMP/android-sdk/ndk/${{ env.NDK_VERSION }}" >> $GITHUB_ENV
          echo "ABI=${{ matrix.abi }}" >> $GITHUB_ENV
          echo "BUILD_DIR=build-${{ matrix.abi }}" >> $GITHUB_ENV

      - name: Restore SDK/NDK cache
        uses: actions/cache@v4
        with:
          path: |
            ${{ runner.temp }}/android-sdk
          key: android-sdk-ndk-${{ env.NDK_VERSION }}-cmake-${{ env.CMAKE_VERSION }}-api-${{ env.ANDROID_API_LEVEL }}-${{ matrix.abi }}
          restore-keys: |
            android-sdk-ndk-

      - name: Install basics
        run: |
          sudo apt-get update
          sudo apt-get install -y unzip wget build-essential

      - name: Prepare Android SDK & cmdline-tools
        if: steps.cache.outputs.cache-hit != 'true'
        run: |
          mkdir -p $ANDROID_SDK_ROOT/cmdline-tools
          cd $ANDROID_SDK_ROOT
          wget -q ${{ env.CMDLINE_TOOLS_ZIP_URL }} -O cmdline-tools.zip
          unzip -q cmdline-tools.zip -d cmdline-tools
          mv cmdline-tools/cmdline-tools cmdline-tools/latest || true
          export PATH="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$PATH"
          yes | sdkmanager --licenses || true
        env:
          PATH: ${{ runner.temp }}/android-sdk/cmdline-tools/latest/bin:$PATH

      - name: Install NDK, platform-tools, platform and CMake
        if: steps.cache.outputs.cache-hit != 'true'
        run: |
          export PATH="$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$PATH"
          sdkmanager "platform-tools" "platforms;android-${{ env.ANDROID_API_LEVEL }}" "ndk;${{ env.NDK_VERSION }}" "cmake;${{ env.CMAKE_VERSION }}"
        env:
          PATH: ${{ runner.temp }}/android-sdk/cmdline-tools/latest/bin:$PATH

      - name: Configure (cmake)
        run: |
          export ANDROID_NDK_HOME=$ANDROID_NDK_HOME
          export ABI=$ABI
          export BUILD_DIR=$BUILD_DIR
          export CPU_TUNE="cortex-a53"
          export CFLAGS="-O3 -fomit-frame-pointer -march=armv8-a -mtune=${CPU_TUNE} -ffast-math"
          export CXXFLAGS="${CFLAGS} -fno-exceptions -fno-rtti"
          mkdir -p $BUILD_DIR
          cmake -S . -B $BUILD_DIR \
            -DANDROID_ABI=${ABI} \
            -DANDROID_NDK=${ANDROID_NDK_HOME} \
            -DANDROID_PLATFORM=android-${{ env.ANDROID_API_LEVEL }} \
            -DCMAKE_TOOLCHAIN_FILE=${ANDROID_NDK_HOME}/build/cmake/android.toolchain.cmake \
            -DCMAKE_BUILD_TYPE=Release \
            -DCMAKE_C_FLAGS="${CFLAGS}" \
            -DCMAKE_CXX_FLAGS="${CXXFLAGS}"
        shell: bash

      - name: Build (cmake)
        run: |
          export BUILD_DIR=$BUILD_DIR
          cmake --build $BUILD_DIR --config Release -j$(nproc)
        shell: bash

      - name: Strip native libraries
        run: |
          export LLVM_STRIP=${ANDROID_NDK_HOME}/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip
          if [ -d "$BUILD_DIR" ]; then
            find $BUILD_DIR -type f -name "*.so" -print0 | xargs -0 -r $LLVM_STRIP --strip-unneeded || true
          fi
        shell: bash

      - name: Collect artifacts
        run: |
          mkdir -p artifacts/${ABI}
          cp -r $BUILD_DIR/lib* artifacts/${ABI}/ 2>/dev/null || true
          cp -r $BUILD_DIR/bin* artifacts/${ABI}/ 2>/dev/null || true
          find $BUILD_DIR -type f -name "*.so" -exec cp --parents {} artifacts/${ABI}/ \; || true
          echo "ABI=${ABI}" > artifacts/${ABI}/build-info.txt
          echo "NDK=${{ env.NDK_VERSION }}" >> artifacts/${ABI}/build-info.txt
          echo "CMake=${{ env.CMAKE_VERSION }}" >> artifacts/${ABI}/build-info.txt
        shell: bash

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: whisper-android-${{ matrix.abi }}
          path: artifacts/${{ matrix.abi }}import os

from setuptools import setup, find_packages

install_requires = [
    "Cython",
    "dtw-python",
    "openai-whisper",
]

required_packages_filename = os.path.join(os.path.dirname(__file__), "requirements.txt")
if os.path.exists(required_packages_filename):
    install_requires2 = [l.strip() for l in open(required_packages_filename).readlines()]
    assert install_requires == install_requires2, f"requirements.txt is not up-to-date: {install_requires} != {install_requires2}"

version = None
license = None
with open(os.path.join(os.path.dirname(__file__), "whisper_timestamped", "transcribe.py")) as f:
    for line in f:
        if line.strip().startswith("__version__"):
            version = line.split("=")[1].strip().strip("\"'")
            if version and license:
                break
        if line.strip().startswith("__license__"):
            license = line.split("=")[1].strip().strip("\"'")
            if version and license:
                break
assert version and license

description="Multi-lingual Automatic Speech Recognition (ASR) based on Whisper models, with accurate word timestamps, access to language detection confidence, several options for Voice Activity Detection (VAD), and more."

setup(
    name="whisper-timestamped",
    py_modules=["whisper_timestamped"],
    version=version,
    description=description,
    long_description=description+"\nSee https://github.com/linto-ai/whisper-timestamped for more information.",
    long_description_content_type='text/markdown',
    python_requires=">=3.7",
    author="Jeronymous",
    url="https://github.com/linto-ai/whisper-timestamped",
    license=license,
    packages=find_packages(exclude=["tests*"]),
    install_requires=install_requires,
    entry_points = {
        'console_scripts': [
            'whisper_timestamped=whisper_timestamped.transcribe:cli',
            'whisper_timestamped_make_subtitles=whisper_timestamped.make_subtitles:cli'
        ],
    },
    include_package_data=True,
    extras_require={
        'dev': ['matplotlib==3.7.4', 'transformers'],
        'vad_silero': ['onnxruntime', 'torchaudio'],
        'vad_auditok': ['auditok'],
        'test': ['jsonschema'],
    },
)
