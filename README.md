# Yapboz Masası

Tarayıcıda çalışan bir yapboz oyunu. Kendi resmini yükle, parçalara ayır ve yeniden birleştir.

**Oyna:** https://antonybo056.github.io/yapboz-masasi/

## Özellikler

- Kendi resmini yükle (dosya seç, sürükle-bırak veya Ctrl+V ile yapıştır) ya da örnek resimlerden birini seç
- 4 zorluk seviyesi: Kolay (~12), Orta (~35), Zor (~70), Uzman (~150 parça)
- Girintili ve çıkıntılı gerçek yapboz parçaları
- Parçalar doğru komşularına ya da tahtadaki yerlerine yaklaşınca otomatik oturur, birleşenler grup halinde taşınır
- Süre, hamle sayacı ve ilerleme göstergesi
- Önizleme, silik resim ipucu, parçaları yeniden dağıtma, duraklatma
- Her zorluk için en iyi süre ve en az hamle rekoru (tarayıcıda saklanır)
- Telefon ve tablette dokunmatik destek

## Kısayollar (tarayıcı sürümü)

| Tuş | İşlev |
| --- | --- |
| P | Duraklat / devam et |
| S | Silik resmi aç/kapat |
| Ö | Önizlemeyi aç/kapat |

## Çalıştırma

İki sürümü var: tarayıcı sürümü ve Python sürümü.

### Tarayıcı sürümü

Kurulum gerekmez. `yapboz.html` dosyasını tarayıcıda açman yeterli.

### Python sürümü (pygame)

Python 3.8 veya üstü gerekir.

```bash
pip install -r requirements.txt
python yapboz.py
```

- Oyun açılınca parçalar karışık halde gelir ve süre başlar.
- Kendi resmini yüklemek için **Yeni oyun** düğmesine, ardından **Resim yükle**'ye bas ya da resim dosyasını pencereye sürükleyip bırak.
- Rekorlar ve ayarlar oyunun yanındaki `yapboz_rekorlar.json` dosyasına kaydedilir.

| Tuş | İşlev |
| --- | --- |
| P | Duraklat / devam et |
| S | Silik resmi aç/kapat |
| O | Önizlemeyi aç/kapat |
| D | Tek parçaları yeniden dağıt |
| N | Yeni oyun ekranı |
| Enter | Kurulum ekranında oyunu başlat |
| Esc | Geri dön / çık |
