# Desktop Assistant

Desktop AI assistant — chat GUI, avatar mode, and built-in screen-control tools.

## Features

- **Chat (GUI) mode** — Ollama-style chat interface, tool calling, SQLite history
- **Avatar mode** — pixel-art avatar, speech bubble, state animations (idle/thinking/working/speaking/error)
- **Mode selection** — chosen on first launch; persisted to `config/ui.json`; switchable from the menu (via restart)
- **Theme** — dark / light; instant switch
- **Language** — Turkish / English; instant switch
- **Screen control** — screenshot, OCR, mouse/keyboard, window management; the server ships embedded in the package, no separate install required

## Installation

### Linux (`.deb`)

```bash
sudo dpkg -i desktop-assistant_<version>_amd64.deb
```

### Linux (portable tar.gz)

```bash
tar -xzf desktop-assistant_<version>_linux_amd64.tar.gz
./desktop-assistant/desktop-assistant
```

### Windows (`.zip`)

Extract `desktop-assistant_<version>_windows_x64.zip` and run `desktop-assistant.exe`.

## First Run

On first launch the app offers a mode choice (Chat GUI / Avatar). The selection is written to `config/ui.json` and can be changed from the right-click menu or the GUI sidebar.

Provider (Groq, NVIDIA, Google, Ollama, …) and API keys are configured in the **Settings** window.

## Configuration Locations

When running from the source tree (development):

| File | Location |
|---|---|
| Settings | `config/settings.json` |
| Secret keys | `config/secrets.json` (0600) |
| UI preferences | `config/ui.json` |
| History | `~/.local/share/desktop-assistant/history.db` |

In a packaged (frozen) build, settings move to the user config directory:

| OS | Location |
|---|---|
| Linux | `~/.config/desktop-assistant/` |
| Windows | `%APPDATA%\desktop-assistant\` |

`config/secrets.json` is never included in the package or the repository.

## Building from Source

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-packaging.txt
.venv/bin/pytest tests -q          # run all tests
.venv/bin/python -m ui.app         # launch the app
```

### Packaging (Linux)

```bash
bash packaging/build_linux.sh      # PyInstaller + tar.gz + deb (requires nfpm)
```

### Screen Control

The screen-control client and server are embedded under `vendor/sc_server/`. When screen control is enabled and port 8745 is free, the app spawns itself as a subprocess with the `--serve-screen-control` flag. Tokens and API keys are stored in the user configuration directory.

## License

MIT — see [LICENSE](LICENSE).

---
---

# Masaüstü Asistan (Türkçe)

Masaüstü AI asistanı — sohbet GUI'si, avatar modu ve yerleşik ekran kontrolü araçları.

## Özellikler

- **Sohbet (GUI) modu** — Ollama tarzı sohbet arayüzü, araç (tool) çağırma, SQLite geçmiş
- **Avatar modu** — pixel-art avatar, konuşma balonu, durum animasyonları (idle/thinking/working/speaking/error)
- **Mod seçimi** — ilk açılışta seçim; `config/ui.json`'a kalıcı olarak yazılır; menüden anında geçiş (yeniden başlatma ile)
- **Tema** — karanlık / açık; anında geçiş
- **Dil** — Türkçe / İngilizce; anında geçiş
- **Ekran kontrolü** — screenshot, OCR, fare/klavye, pencere yönetimi; sunucu paketin içinde gömülü olarak gelir, ayrı kurulum gerektirmez

## Kurulum

### Linux (`.deb`)

```bash
sudo dpkg -i desktop-assistant_<version>_amd64.deb
```

### Linux (taşınabilir tar.gz)

```bash
tar -xzf desktop-assistant_<version>_linux_amd64.tar.gz
./desktop-assistant/desktop-assistant
```

### Windows (`.zip`)

`desktop-assistant_<version>_windows_x64.zip` dosyasını çıkarıp `desktop-assistant.exe`'yi çalıştırın.

## İlk Çalıştırma

Uygulama ilk açılışta mod seçimi sunar (Sohbet GUI / Avatar). Seçim `config/ui.json`'a yazılır; sağ tık menüsünden veya GUI kenar çubuğundan değiştirilebilir.

Sağlayıcı (Groq, NVIDIA, Google, Ollama, …) ve API anahtarları **Ayarlar** penceresinden yapılandırılır.

## Yapılandırma Konumları

Kaynak ağaçtan (development) çalışırken:

| Dosya | Konum |
|---|---|
| Ayarlar | `config/settings.json` |
| Gizli anahtarlar | `config/secrets.json` (0600) |
| UI tercihleri | `config/ui.json` |
| Geçmiş | `~/.local/share/desktop-assistant/history.db` |

Paketlenmiş (frozen) sürümde ayarlar kullanıcı dizinine taşınır:

| İşletim Sistemi | Konum |
|---|---|
| Linux | `~/.config/desktop-assistant/` |
| Windows | `%APPDATA%\desktop-assistant\` |

`config/secrets.json` ne paketin içine ne de depoya dahil edilir.

## Kaynaktan Derleme

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-packaging.txt
.venv/bin/pytest tests -q          # tüm testler
.venv/bin/python -m ui.app         # uygulamayı başlat
```

### Paket Oluşturma (Linux)

```bash
bash packaging/build_linux.sh      # PyInstaller + tar.gz + deb (nfpm gerekir)
```

### Ekran Kontrolü

Ekran kontrolü istemcisi ve sunucusu `vendor/sc_server/` altında gömülüdür. Uygulama, ekran kontrolü etkinse ve port 8745 boşta değilse kendini `--serve-screen-control` bayrağıyla alt süreç olarak başlatır. Token ve API anahtarları kullanıcı yapılandırma dizininde saklanır.

## Lisans

MIT — bkz. [LICENSE](LICENSE).
