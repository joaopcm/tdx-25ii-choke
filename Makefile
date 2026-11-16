PREFIX ?= $(HOME)/.local
BIN := $(PREFIX)/bin/tdx-choke
AGENT := $(HOME)/Library/LaunchAgents/com.joaopcm.tdx-choke.plist
LOG := $(HOME)/Library/Logs/tdx-choke.log

build/tdx-choke: converter/main.swift
	mkdir -p build
	swiftc -O -o $@ $<

install: build/tdx-choke
	install -d $(PREFIX)/bin $(dir $(AGENT))
	install -m 755 build/tdx-choke $(BIN)
	sed -e 's|@BIN@|$(BIN)|' -e 's|@LOG@|$(LOG)|' converter/com.joaopcm.tdx-choke.plist > $(AGENT)
	launchctl bootout gui/$$(id -u) $(AGENT) 2>/dev/null || true
	launchctl bootstrap gui/$$(id -u) $(AGENT)

uninstall:
	launchctl bootout gui/$$(id -u) $(AGENT) 2>/dev/null || true
	rm -f $(AGENT) $(BIN)

.PHONY: install uninstall
