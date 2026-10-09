# M1 Masaüstü Manuel Checklist

Gerçek masaüstünde, `.venv/bin/python -m ui.app` ile:

- [ ] Avatar sağ-alt köşede görünüyor, arka plan şeffaf
- [ ] Diğer pencerelerin üstünde kalıyor (always-on-top)
- [ ] Idle animasyonu ~6fps sallanıyor
- [ ] Baloncuğa "ekran görüntüsü al" yaz → thinking → working → speaking → idle
- [ ] Tool activity satırı güncelleniyor ("▸ screenshot çalışıyor…")
- [ ] İptal butonu görevi durduruyor, avatar idle'a dönüyor
- [ ] Avatar'a sağ tık → Ayarlar… / Sohbet / Karakter / Çıkış açılıyor
- [ ] Ayarlar'da model değiştir → Kaydet → kalıcı (settings.json)
- [ ] Sohbet menüden baloncuğu açıp kapatıyor
- [ ] Karakter menüsü avatar klasörü listeliyor (yeniden başlatma notu)
- [ ] Görev sırasında Çıkış → ≤2sn'de temiz kapanış
- [ ] Ağ bağlantısını kes → hata mesajı → avatar ~3sn kırmızı → idle'a döner
- [ ] M0 CLI hâlâ çalışıyor (`cli.py` bozulmadı)
