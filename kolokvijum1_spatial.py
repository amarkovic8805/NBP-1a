"""
Jednostavna simulacija kretanja dostavljača duž ruta koje se odredjuju preko openrouteservice-a korišćenjem Open Street Maps.

Pokretanje:  python kolokvijum1_spatial.py
Fajl projekat_api.py mora biti u istom folderu (odatle se uzimaju lokacije,
ORS klijent i pozadinska mapa).
"""
from datetime import datetime, timedelta
from rtree import index


import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import math


from projekat_api import (
    iscrtaj_korak_simulacije,
    dohvati_pozadinsku_mapu_beograda,
    iscrtaj_staticnu_sliku,
    kreiraj_dostavljace,
    kreiraj_pokretne_elemente_na_mapi,
    pripremi_trajektorije_dostave,
)

# Globalne promenljive za indekse
index2d = None
index3d = None
poslednja = {}
brojac3d = 0


LAT = 44.8
M_PO_STEPENU = 111320.0

def u_metre(lon, lat):
    return lon * M_PO_STEPENU * math.cos(math.radians(LAT)), lat * M_PO_STEPENU


def azuriraj_prikaz(frejm):
    vreme = POCETAK_SIMULACIJE + timedelta(seconds=frejm * KORAK_SIMULACIJE_S)

    rezim_rada["vreme"] = vreme

    # simulacija pomeraja dostavljaca u trenutku t = broj_frejma * KORAK_SIMULACIJE_SEKUNDI
    pozicije_dostavljaca = korak_simulacije(dostavljaci, vreme, POCETAK_SIMULACIJE)   

    # poziv funkcije za azuriranje lokacija dostavljaca
    azuriraj_lokacije_dostavljaca(pozicije_dostavljaca)
    
    return (*iscrtaj_korak_simulacije(markeri, brojevi, sat, pozicije_dostavljaca, vreme), info) # crtanje novih pozicija dostavljaca i ažuriranje sata


    
# ---------------------------------------------------------------------------
# Simulacija pomeranja dostavljača (bez crtanja)
# ---------------------------------------------------------------------------

def pozicija_u_trenutku(d, t):
    """Pozicija dostavljača u trenutku t (linearna interpolacija između tačaka rute).
    Pre polaska stoji na početnoj lokaciji, a posle dolaska na odredišnoj lokaciji."""
    
    return np.interp(t, d["vremena"], d["lon"]), np.interp(t, d["vremena"], d["lat"])


def korak_simulacije(dostavljaci, vreme, pocetak_simulacije):
    """Jedan korak simulacije: pomera sve dostavljače na poziciju u trenutku
    vreme (datetime) i ažurira njihov status.

    Vraća listu novih pozicija, po jedan zapis za svakog dostavljača,
    istim redosledom kao u listi dostavljaci. Ti zapisi su ono što će se
    kasnije upisivati u prostorni / prostorno-vremenski indeks."""
    
    t = (vreme - pocetak_simulacije).total_seconds()   # trajektorije su u sekundama od početka


    pozicije_dostavljaca = []
    for d in dostavljaci:
        lon, lat = pozicija_u_trenutku(d, t)

        if t < d["vremena"][0]:
            status = "ceka"
        elif t < d["vremena"][-1]:
            status = "vozi"
        else:
            status = "stigao"

        d["trenutni_lon"], d["trenutni_lat"], d["status"] = float(lon), float(lat), status
        pozicije_dostavljaca.append({"id": d["id"], "vreme": vreme, "lon": float(lon), "lat": float(lat), "status": status})
        
        # pozicije_dostavljaca je lista rečnika, po jedan za svakog dostavljača, sa sledećim ključevima:
        # "id" – identifikator dostavljača (int)
        # "vreme" – trenutak simulacije (datetime)
        # "lon" – geografska dužina (float)
        # "lat" – geografska širina (float)
        # "status" – string: "ceka", "vozi" ili "stigao"

        # Primer jednog zapisa za novu poziciju dostavljača: 
        # {"id": 1, "vreme": datetime(2026, 1, 1, 12, 0, 10), "lon": 20.123456, "lat": 44.987654, "status": "vozi"}


    return pozicije_dostavljaca

def pritisnut_taster(event):
    """Taster 1, 2 ili 3 bira zadatak."""
    if event.key in ("1", "2", "3"):
        rezim_rada["zadatak"] = int(event.key)
        rezim_rada["tacke"] = []
        uputstvo = "Kliknite na prvo teme" if rezim_rada["zadatak"] == 3 else "Kliknite na mapu"
        info.set_text(f"{OPISI_ZADATAKA[rezim_rada['zadatak']]}\n{uputstvo}")
        print(OPISI_ZADATAKA[rezim_rada["zadatak"]])
    
def klik_na_mapi(event):
    if event.inaxes is not ax or event.button != 1:   # samo levi klik unutar mape
        return
    if rezim_rada["zadatak"] is None:
        print("Prvo pritisnite 1, 2 ili 3 za izbor zadatka")
        return
    # Ose su u EPSG:4326, pa je mesto klika direktno (lon, lat)

    lon, lat = float(event.xdata), float(event.ydata)
    if rezim_rada["zadatak"] == 1:
        zadatak_1(lon, lat, poluprecnik_m=POLUPRECNIK_M)
    elif rezim_rada["zadatak"] == 2:
        zadatak_2(lon, lat, k=K_NAJBLIZIH)
    elif rezim_rada["zadatak"] == 3:
        rezim_rada["tacke"].append((lon, lat))
        if len(rezim_rada["tacke"]) == 1:
            info.set_text(f"{OPISI_ZADATAKA[3]}\nKliknite na drugo teme")
        else:
            (lon1, lat1), (lon2, lat2) = rezim_rada["tacke"]
            rezim_rada["tacke"] = []
            info.set_text(f"{OPISI_ZADATAKA[3]}\nKliknite na prvo teme")
            zadatak_3(min(lon1, lon2), min(lat1, lat2), max(lon1, lon2), max(lat1, lat2),
                        rezim_rada["vreme"] - timedelta(minutes=INTERVAL_MIN), rezim_rada["vreme"])
            


def pocetna_slika():
    return (markeri, sat, info, *brojevi)

def zadatak_1(lon, lat, poluprecnik_m=200):
    """Zadatak 1: koji dostavljači su trenutno u krugu od poluprecnik_m metara
    oko tačke (lon, lat)?"""
    
    print(f"Zadatak 1: Dostavljači u krugu od poluprečnika {poluprecnik_m} m od tačke: lat {lat:.6f}, lon {lon:.6f}, su:")

    x,y = u_metre(lon, lat)
    
    results = list(index2d.intersection((x-poluprecnik_m, y-poluprecnik_m, x+poluprecnik_m, y+poluprecnik_m)))

    filtered = []

    for id in results:
        p = poslednja[id]
        dist = math.hypot(p["x"] - x, p["y"] - y)
        if(dist <= poluprecnik_m):
            filtered.append(id)

   
    # Ispisivanje rezultata, npr.:
    # Dostavljači u krugu od poluprečnika 200 m od tačke: lat 44.987654, lon 20.123456, su:
    # id: 1, status: vozi, lokacija: (lat 44.987654, lon 20.123456)
    # id: 5, status: čeka, lokacija: (lat 44.987654, lon 20.123456)
    # id: 12, status: stigao, lokacija: (lat 44.987654, lon 20.123456)
    # itd.  

    if not filtered:
            print("Nema dostavljača u krugu.")
            return
    
    for id in filtered:
            p = poslednja[id]
            print(f"id: {id}, status: {p['status']}, lokacija: (lat {p['lat']:.6f}, lon {p['lon']:.6f})")


def zadatak_2(lon, lat, k=3):
    """Zadatak 2: kojih k dostavljača je trenutno najbliže tački (lon, lat)?"""
    
    print(f"Zadatak 2: Najbliža {k} dostavljača od tačke: lat {lat:.6f}, lon {lon:.6f}, su:")

    x,y = u_metre(lon, lat)

    location = (x, y) + (x, y)
    
    results = list(index2d.nearest(location,num_results=k))

    # Ispisivanje rezultata, npr.:
    # Najbližih 3 dostavljača od tačke: lat 44.987654, lon 20.123456, su:
    # id: 5, status: čeka, lokacija: (lat 44.987654, lon 20.123456), udaljenost: 150 m
    # id: 1, status: vozi, lokacija: (lat 44.987654, lon 20.123456), udaljenost: 180 m
    # id: 12, status: stigao, lokacija: (lat 44.987654, lon 20.123456), udaljenost: 190 m

    for id in results:
        p = poslednja[id]
        dist =  math.hypot(p["x"] - x, p["y"] - y)
        print(f"id: {id}, status: {p['status']}, lokacija: (lat {p['lat']:.6f}, lon {p['lon']:.6f}), udaljenost: {dist:.0f} m")

    

def zadatak_3(zapad, jug, istok, sever, vreme_od, vreme_do):
    """Zadatak 3: koji dostavljači su bili u pravougaoniku
    [zapad, istok] x [jug, sever] u intervalu [vreme_od, vreme_do]?"""
    
    print(f"Zadatak 3: Dostavljači koji su u poslednja {INTERVAL_MIN} minuta bili u rejonu: lon {zapad:.6f} – {istok:.6f}, lat {jug:.6f} – {sever:.6f}, "
          f"vreme {vreme_od:%H:%M:%S} – {vreme_do:%H:%M:%S}")
    
    x_zapad, y_jug = u_metre(zapad, jug)
    x_istok, y_sever = u_metre(istok, sever)

    t_od = (vreme_od - POCETAK_SIMULACIJE).total_seconds()
    t_do = (vreme_do - POCETAK_SIMULACIJE).total_seconds()

    results = list(index3d.intersection((x_zapad, y_jug, t_od, x_istok, y_sever, t_do), objects=True))

    poslednji_u_oblasti = {}

    for item in results:
        id, status, lon_z, lat_z = item.object
        t = item.bbox[2] # bbox = [x, y, t, x, y, t] - bbox[2] je t
        if id not in poslednji_u_oblasti or t > poslednji_u_oblasti[id][0]:
            poslednji_u_oblasti[id] = (t, status, lon_z, lat_z)

    if not poslednji_u_oblasti:
        print("Nema dostavljača u oblasti u zadatom intervalu.")
        return

    for id, (t, status, lon_z, lat_z) in poslednji_u_oblasti.items():
        vreme_z = POCETAK_SIMULACIJE + timedelta(seconds=t) # Vraćanje nazad u datetime radi ispisa vremena
        print(f"id: {id}, status: {status}, lokacija: (lat {lat_z:.6f}, lon {lon_z:.6f}), vreme: {vreme_z:%H:%M:%S}")
    # Ispisivanje rezultata, npr.:
    # Dostavljači koji su u poslednjih 2 minuta bili u rejonu:
    # Jedan red po dostavljaču, sa poslednjom pozicijom u oblasti
    # lon 20.123456 – 20.223456, lat 44.987654 – 44.987754, vreme 12:00:10 – 12:02:10
    # id: 5, status: čeka, lokacija: (lat 44.987654, lon 20.123456), vreme: 12:01:05
    # id: 1, status: vozi, lokacija: (lat 44.987654, lon 20.123456), vreme: 12:01:30
    # id: 12, status: stigao, lokacija: (lat 44.987654, lon 20.123456), vreme: 12:02:00
    # itd.


# ---------------------------------------------------------------------------
# Azuriranje prostornog / prostorno-vremenskog indeksa sa lokacijama dostavljača u trenutku t
# ---------------------------------------------------------------------------
def azuriraj_lokacije_dostavljaca(pozicije_dostavljaca:list):
    """Ovde treba da se ažurira prostorno / prostorno-vremenski indeks 
    sa lokacijama dostavljača.
    Ova funkcija se poziva u svakom koraku simulacije, sa listom novih pozicija
    dostavljača u trenutku t = frejm * KORAK_SIMULACIJE_S."""
    # pozicije_dostavljaca je lista rečnika, po jedan za svakog dostavljača, sa sledećim ključevima:
    # "id" – identifikator dostavljača (int)
    # "vreme" – trenutak simulacije (datetime)
    # "lon" – geografska dužina (float)
    # "lat" – geografska širina (float)
    # "status" – string: "ceka", "vozi" ili "stigao"
    # Primer jednog zapisa za poziciju dostavljača: 
    # {"id": 1, "vreme": datetime(2026, 1, 1, 12, 0, 10), "lon": 20.123456, "lat": 44.987654, "status": "vozi"}

    global index3d, brojac3d

    for z in pozicije_dostavljaca:
        x,y = u_metre(z["lon"], z["lat"])
        t = (z["vreme"] - POCETAK_SIMULACIJE).total_seconds()
        p = poslednja[z["id"]]

        if(x,y) != (p["x"],p["y"]):
            index2d.delete(z["id"], (p["x"], p["y"], p["x"], p["y"]))
            index2d.insert(z["id"], (x, y, x, y))

        if p["t"] is None or t > p["t"]:
            index3d.insert(brojac3d, (x, y, t, x, y, t), obj=(z["id"], z["status"], z["lon"], z["lat"]))
            brojac3d += 1
        
        p.update(x=x, y=y, lon=z["lon"], lat=z["lat"], status=z["status"], t=t)

def inicijalizacija_indeksa(dostavljaci):
    """Ovde treba da se incijalizuje prostorni / prostorno-vremenski indeks 
    sa početnim pozicijama dostavljača (pre polaska)."""
    # dostavljaci je lista rečnika, po jedan za svakog dostavljača, sa sledećim ključevima:
    # "id" – identifikator dostavljača (int)
    # "trenutni_lon" – trenutna geografska dužina (float)
    # "trenutni_lat" – trenutna geografska širina (float)
    # "status" – trenutni status dostavljača: "ceka", "vozi" ili "stigao"
    # itd. 
    global index2d, index3d, poslednja, brojac3d
    
    index2d = index.Index()

    p = index.Property()
    p.dimension = 3
    index3d = index.Index(properties=p)

    poslednja = {}
    brojac3d = 0

    for d in dostavljaci:
        x,y = u_metre(d["trenutni_lon"], d["trenutni_lat"])
        index2d.insert(d["id"], (x, y, x, y))

        poslednja[d["id"]] = {
            "x": x, "y": y,
            "lon": d["trenutni_lon"], "lat": d["trenutni_lat"],
            "status": d["status"],
            "t": None,
        }


# ---------------------------------------------------------------------------
KORAK_SIMULACIJE_S = 1          # simulirane sekunde po jednom frejmu

POLUPRECNIK_M = 200      # Zadatak 1
K_NAJBLIZIH = 3          # Zadatak 2
INTERVAL_MIN = 2         # Zadatak 3

OPISI_ZADATAKA = {
    1: f"Zadatak 1 – Dostavljači u krugu poluprečnika od {POLUPRECNIK_M} m oko tačke",
    2: f"Zadatak 2 – Najbliža {K_NAJBLIZIH} dostavljača tački na mapi",
    3: f"Zadatak 3 – Dostavljači u pravougaoniku u poslednja {INTERVAL_MIN} min",
}

# Vreme početka simulacije (prvi frejm = 0 sekundi od ovog vremena)
# U ovom primeru simulacija počinje 1. novembra 2026. u 12:00:00
# Vreme se ispisuje u gornjem levom uglu mape
POCETAK_SIMULACIJE = datetime(2026, 11, 1, 12, 0, 0)   

# izabrani zadatak, kliknuti uglovi (zadatak 3) i trenutno vreme simulacije
rezim_rada = {"zadatak": None, "tacke": [], "vreme": POCETAK_SIMULACIJE}  


if __name__ == "__main__":

    BROJ_DOSTAVLJACA = 40
    RNG_SEED = 42             # isti broj → isti dostavljači u svakom pokretanju; None → svaki put drugi
    
    # 1) Dostavljači i njihove trajektorije (jednom, pre simulacije)
    # dostavljaci je lista rečnika, po jedan za svakog dostavljača
    dostavljaci = kreiraj_dostavljace(BROJ_DOSTAVLJACA, rng_seed=RNG_SEED)
    
    pripremi_trajektorije_dostave(dostavljaci)

    # ===============================
    #  inicijalizacija prostornog / prostorno-vremenskog indeksa sa početnim pozicijama dostavljača
    # =================================
    inicijalizacija_indeksa(dostavljaci)
   

    # 2) Slika: statični deo (mapa, rute) i markeri koji predstavljaju dostavljače i pomeraju se (dostavljači, sat)
    dohvati_pozadinsku_mapu_beograda()

    fig, ax = iscrtaj_staticnu_sliku(dostavljaci)
    
    markeri, brojevi, sat = kreiraj_pokretne_elemente_na_mapi(ax, dostavljaci)

    # info: izabrani zadatak i uputstvo, ispod sata
    info = ax.text(0.02, 0.91, "Pritisnite 1, 2 ili 3 za izbor zadatka",
                   transform=ax.transAxes, fontsize=10, va="top",
                   bbox=dict(facecolor="white", alpha=0.8), zorder=7)
    
    
    # Reagovanje kada se pritisne taster 1, 2 ili 3: pozvace se funkcija pritisnut_taster(event), sa event.key = "1", "2" ili "3"
    fig.canvas.mpl_connect("key_press_event", pritisnut_taster)
    # Reagovanje kada se klikne na mapu: pozvace se funkcija klik_na_mapi(event), sa event objektom koji sadrzi geokoordinate tačke gde je kliknuto
    fig.canvas.mpl_connect("button_press_event", klik_na_mapi)


    fig.tight_layout()

    # 3) Svaki frejm animacije = jedan korak simulacije pomeranja dostavljača + crtanje tog koraka
    # U svakom koraku simulacije se poziva azuriraj_prikaz(frejm), koji računa pozicije dostavljača u trenutku t = frejm * KORAK_SIMULACIJE_S
    # i poziva funkciju azuriraj_lokacije_dostavljaca() gde treba da se ažurira prostorni / prostorno-vremenski indeks sa tim pozicijama.

    # anim mora ostati u promenljivoj, inače ga Python obriše i animacija stane.
    # init_func samo vraća elemente, bez koraka simulacije. Bez njega matplotlib
    # na početku (i pri promeni veličine prozora) poziva azuriraj_prikaz još jednom,
    # pa bi se pozicije za t = 0 upisale u indeks više puta.
    anim = FuncAnimation(fig, azuriraj_prikaz, frames=None, init_func=pocetna_slika,
                         interval=33, blit=True, cache_frame_data=False)
    plt.show()
