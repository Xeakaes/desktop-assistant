# Desktop Assistant

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

`desktop-assistant_<version>_windows_amd64.zip` dosyasını çıkarıp `desktop-assistant.exe`'yi çalıştırın.

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
