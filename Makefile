CC = clang
USB_PREFIX ?= /opt/homebrew
CFLAGS = -O2 -Wall -Wextra -Werror -std=c11
CPPFLAGS += -I$(USB_PREFIX)/include/libusb-1.0 -Isdk
LDFLAGS += -L$(USB_PREFIX)/lib
.PHONY: all clean test
all: artifacts/libdili.dylib
artifacts/libdili.dylib: sdk/dili.c sdk/color.c sdk/dili.h
	mkdir -p artifacts
	$(CC) $(CFLAGS) $(CPPFLAGS) -dynamiclib sdk/dili.c sdk/color.c $(LDFLAGS) -lusb-1.0 -install_name @rpath/libdili.dylib -o $@
clean:
	rm -f artifacts/libdili.dylib
artifacts/test-native: tests/native_sdk.c sdk/dili.c sdk/dili.h
	mkdir -p artifacts
	$(CC) $(CFLAGS) $(CPPFLAGS) tests/native_sdk.c -o $@
artifacts/test-color: tests/native_color.c sdk/color.c sdk/dili.h
	mkdir -p artifacts
	$(CC) $(CFLAGS) $(CPPFLAGS) tests/native_color.c sdk/color.c -o $@
test: all artifacts/test-native artifacts/test-color
	artifacts/test-native
	artifacts/test-color
	python3 -m unittest discover -s tests
	node --test tests/geometry.test.js
