"""Download demo photos to local public assets (Unsplash source attribution in README)."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
photos = {
    'burger': 'photo-1568901346375-23c9450c58cd',
    'double': 'photo-1550547660-d9450f859349',
    'bacon': 'photo-1561758033-d89a9ad46330',
    'chicken': 'photo-1606755962773-d324e0a13086',
    'fries': 'photo-1573080496219-bb080dd4f877',
    'rings': 'photo-1639024471283-03518883512d',
    'salad': 'photo-1512621776951-a57141f2eefd',
    'cola': 'photo-1622483767028-3f66f32aef97',
    'lemonade': 'photo-1544145945-f90425340c7e',
    'coffee': 'photo-1461023058943-07fcbe16d735',
    'shake': 'photo-1572490122747-3968b75cc699',
}
root=Path(__file__).resolve().parents[1]/'frontend/public/images'
root.mkdir(parents=True,exist_ok=True)
def download(item):
    name,photo=item
    result=subprocess.run(['curl','-fLsS','--max-time','40',f'https://images.unsplash.com/{photo}?auto=format&fit=crop&w=1000&q=85','-o',str(root/f'{name}.jpg')],capture_output=True)
    print(name, 'OK' if result.returncode==0 else result.stderr.decode())
with ThreadPoolExecutor(max_workers=5) as pool: list(pool.map(download,photos.items()))
