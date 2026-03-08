import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from monitoring.metrics import metrics

metrics.mesaj_sayac("sohbet")
metrics.basari_kaydet()
metrics.yanit_sure_kaydet(1.5)
print(metrics.ozet_metni())
print("metrics OK")
