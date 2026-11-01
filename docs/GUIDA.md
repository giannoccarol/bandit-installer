# Installer Android per Lumia 1520: guida

[English](GUIDE.md) · [README](../README.md)

Questa guida porta passo per passo un Lumia 1520 con Windows 10 Mobile a un telefono che avvia
**lk1st** (il bootloader Android) dal proprio boot manager.

> **Sperimentale.** Oggi l'installer prepara la catena di avvio e verifica che lk1st risponda in
> fastboot. Android non si può ancora installare: partizioni Android e ROM (fase 2) arriveranno
> quando il layout delle partizioni sarà definitivo. Windows resta sul telefono e continua a funzionare.

## Indice

1. [Cosa serve](#1-cosa-serve)
2. [Download](#2-download)
3. [Preparare il PC](#3-preparare-il-pc)
4. [Sbloccare il telefono e metterlo in mass storage](#4-sbloccare-il-telefono-e-metterlo-in-mass-storage)
5. [Avviare l'installer](#5-avviare-linstaller)
6. [Installazione completa, passo per passo](#6-installazione-completa-passo-per-passo)
7. [Dopo l'installazione](#7-dopo-linstallazione)
8. [Strumenti avanzati](#8-strumenti-avanzati)
9. [Tornare indietro](#9-tornare-indietro)
10. [Problemi comuni](#10-problemi-comuni)
11. [File e opzioni](#11-file-e-opzioni)

## 1. Cosa serve

- Un **Nokia Lumia 1520** (RM-937, RM-938 o RM-940) con Windows Phone 8.1 o Windows 10 Mobile.
- Un **PC Windows 10/11** per lo sblocco con [WPinternals](https://github.com/ReneLergner/WPinternals).
  L'installer funziona su quel PC oppure su un PC **Linux**.
- Un buon cavo USB (uno difettoso si nota come «due letture diverse» durante il backup) e la
  batteria sopra il 50%.
- Spazio libero sul PC: circa 1 GB per il backup di base, più la copia compressa dell'intero telefono
  se tieni l'immagine completa (consigliata: da qualche GB a decine di GB, secondo quanto è pieno).
- Da 30 a 90 minuti, quasi tutti per il backup completo.

## 2. Download

Dalla [pagina delle release](https://github.com/giannoccarol/bandit-installer/releases) scarica il
pacchetto per il tuo sistema e, se vuoi controllarlo, `SHA256SUMS`:

| Sistema | File | Contiene |
|---|---|---|
| Windows (64 bit) | `bandit-installer-<versione>-windows.zip` | l'installer e il suo Python, niente altro da installare |
| Linux | `bandit-installer-<versione>-linux.tar.gz` | l'installer; usa il Python 3 del sistema |

Estrailo in una cartella con abbastanza spazio: backup e log finiscono in `work\` dentro quella
cartella. Su Windows estrai prima tutto lo zip (tasto destro → *Estrai tutto*); non avviarlo
dall'interno dello zip.

## 3. Preparare il PC

### Windows

1. Installa il [driver USB di Google](https://developer.android.com/studio/run/win-usb), perché
   Windows riconosca il telefono in fastboot.
2. Serve **Edge** o **Chrome** (Edge è già in Windows): l'installer si apre in una finestra app di
   quel browser.
3. `fastboot` e `adb` non servono prima: l'installer propone di scaricare i Platform Tools di Google
   nella sua cartella `tools\`.

### Linux

Installa Python 3 (3.8 o successivo), il modulo Python di hivex (per modificare il BCD), util-linux
e il supporto NTFS (per il passo del firmware):

```bash
sudo pacman -S python hivex util-linux ntfs-3g                      # Arch
sudo apt install python3 python3-hivex util-linux ntfs-3g           # Debian, Ubuntu
sudo dnf install python3 python3-hivex util-linux ntfs-3g           # Fedora
```

Per la finestra app serve Chromium, Chrome, Brave o Edge; senza, si apre una scheda del browser
predefinito, e `--text` offre un'interfaccia da terminale. Vanno bene `fastboot` e `adb` della
distribuzione; se mancano, l'installer può scaricare la copia di Google.

## 4. Sbloccare il telefono e metterlo in mass storage

Questa parte si fa con WPinternals su Windows, fuori da questo installer.

1. Segui le istruzioni di WPinternals per **sbloccare il bootloader**.
2. In WPinternals scegli **Switch to Mass Storage Mode**. Il telefono mostra il simbolo USB e le sue
   partizioni compaiono sul PC.
3. È un buon momento per un backup completo del telefono (l'installer può farlo per te).

Dopo lo sblocco puoi spostare il cavo su un PC Linux: il telefono resta in mass storage fino al
riavvio.

## 5. Avviare l'installer

| Sistema | Come |
|---|---|
| Windows | doppio clic su `installer.bat` e accetta la richiesta di amministratore |
| Linux | `./installer.sh` in un terminale; chiede la password tramite `sudo` |

I permessi di amministratore (root) servono per leggere e scrivere il disco del telefono. Per
l'interfaccia in italiano: **Settings → Language → Italiano** (la scelta resta salvata), oppure avvia
con `--lang it`. La finestra mostra:

- a sinistra, un riquadro colorato con lo **stato del telefono** (non collegato, mass storage,
  fastboot, modalità flash…); un clic avvia la diagnostica;
- **Installa**, con le tre modalità e l'avanzamento dell'installazione completa;
- **Strumenti avanzati**, con i singoli passi;
- **Impostazioni**, per lingua, colore d'accento e cartella dati.

La finestra comunica con l'installer tramite un indirizzo locale (`127.0.0.1`) mostrato nel
terminale. Se la finestra non si apre, copia quell'indirizzo in un browser. Chiudere la finestra non
ferma l'installer: usa **Impostazioni → Esci**, oppure Ctrl+C nel terminale.

## 6. Installazione completa, passo per passo

Collega il telefono in mass storage e premi **Inizia** su **Installazione completa**. L'installer
esegue questi passi e li ricorda: se ti fermi, la volta dopo propone di saltare quelli già fatti.

### 6.1 Platform Tools

Se mancano `fastboot` o `adb`, chiede di scaricare i Platform Tools di Google (circa 7 MB).

### 6.2 Backup

Trova il disco del telefono dalla sua tabella delle partizioni e chiede se fare anche l'**immagine
completa compressa**. Poi salva:

- la tabella delle partizioni (GPT primaria e di riserva);
- ogni partizione sotto i 512 MiB (DPP, modem, UEFI, EFIESP…), letta **due volte** e confrontata;
- l'immagine completa, se scelta (20-60 minuti);
- un elenco `SHA256SUMS` di tutto.

Il backup contiene dati personali e del modem (DPP, MODEM_FS*): conservalo e non pubblicarlo mai.

### 6.3 Firmware da Windows

Copia dalle partizioni di Windows il firmware che servirà ad Android (ADSP, Wi-Fi, modem, Venus), le
calibrazioni audio e Wi-Fi, le tabelle ACPI e il registro, e divide i file `.mbn` nel formato
`.mdt` + `.bNN` che Android carica. Sono file Nokia/Microsoft: restano sul tuo PC.

### 6.4 Catena di avvio

È l'unico passo che scrive sul telefono, e solo sulla partizione **EFIESP**.

1. Mostra la configurazione di avvio attuale (BCD).
2. Chiede le **opzioni di avvio**:
   - **lk1st**: la build di lk1st da installare (quella verificata è già selezionata);
   - **Avvia Android all'accensione**: attivo = parte lk1st; disattivo = parte Windows e la voce
     Android resta nel menu;
   - **Volume giù → l'altro sistema**: il tasto volume giù all'accensione avvia il sistema che non è
     quello predefinito (al posto di *Reset My Phone*);
   - **Solo Android**: per quando Windows è già stato rimosso;
   - **Attesa del menu**: secondi di attesa del menu di avvio; 0 = nessun menu.
3. Fa il backup di EFIESP (file e immagine), scrive il nuovo BCD **accanto al backup**, lo rilegge e
   lo verifica: una sola voce nuova, le altre invariate, volume su apre ancora la modalità flash.
4. Mostra il nuovo BCD e chiede di scrivere **INSTALLA** (in inglese **INSTALL**).
5. Scrive BootShim, lk1st e il BCD, e confronta ogni file con il kit.

**Volume su all'accensione apre sempre la modalità flash**: è la via di ritorno con WPinternals, e
l'installer rifiuta ogni configurazione che la cambierebbe.

### 6.5 Riavvio e verifica di lk1st

Riavvia il telefono: esci dalla modalità mass storage in WPinternals, oppure tieni premuti
**accensione + volume giù** per circa 10 secondi, finché vibra. Compare il testo di BootShim, poi lo
schermo resta fermo: questo lk1st non usa il display, quindi è normale.

L'installer aspetta fastboot e dice cosa vede nel frattempo (boot manager di Windows Phone, fastboot,
Qualcomm 9008…). Quando lk1st risponde salva `fastboot getvar all` e il log di lk1st in `work/logs/`.
L'elenco dell'avanzamento mostra i quattro passi completati.

### 6.6 Kernel di prova K1 (facoltativo)

Alla fine propone di avviare in RAM **K1**, il primo kernel bandit (`fastboot boot`). Non viene
scritto nulla sul telefono e al riavvio successivo torna lk1st. K1 non è ancora mai stato avviato su
un telefono: se lo provi, conserva i log che raccoglie.

## 7. Dopo l'installazione

| Fai | Il telefono avvia |
|---|---|
| accensione (Android predefinito) | lk1st in fastboot, schermo fermo |
| accensione con volume giù (se scelto) | Windows 10 Mobile |
| accensione con volume su | modalità flash, per WPinternals |

Con **Avvia Android all'accensione** disattivato, Windows parte come prima e lk1st è nel menu di avvio.

## 8. Strumenti avanzati

Ogni passo dell'installazione completa si può eseguire anche da solo, più alcuni strumenti per lo
sviluppo:

| Strumento | Stato del telefono | Scrive sul telefono |
|---|---|---|
| Backup, Firmware | mass storage | no |
| Catena di avvio | mass storage | solo EFIESP, dopo un backup |
| Verifica lk1st | riavvio → fastboot | no |
| Avvio in RAM | fastboot | no: `fastboot boot` di K1 o di un `boot.img` |
| Log del boot precedente | fastboot | no: ram console e log di lk1st dopo un blocco |
| Scrivi partizione | fastboot | sì, solo partizioni Android (`boot`, `recovery`, `system`…) |
| Ripristino EFIESP | mass storage | sì, da un backup |
| Diagnostica | qualsiasi | no |
| Platform Tools | — | no |

Ogni passo che scrive chiede prima di scrivere una parola (`INSTALLA`, `SCRIVI`, `RIPRISTINA` in
italiano; `INSTALL`, `WRITE`, `RESTORE` in inglese).

## 9. Tornare indietro

- **Dall'installer**: metti il telefono in mass storage (volume su all'accensione, poi WPinternals) e
  usa **Strumenti avanzati → Ripristino EFIESP**. Scegli il backup fatto prima della catena di avvio.
  Su Windows vengono rimessi i file; su Linux puoi anche riscrivere l'immagine intera della partizione.
- **A mano su Linux**, con la partizione smontata e il nome del dispositivo controllato due volte:
  `dd if=work/backups/efiesp-<data>/efiesp-partition.img of=/dev/sdX<n> bs=1M conv=fsync`.
- **A mano su Windows**: scrivi `efiesp-partition.img` su EFIESP con Win32DiskImager.
- **Se il telefono non si avvia affatto**: volume su all'accensione (modalità flash), poi WPinternals
  o Windows Device Recovery Tool.

## 10. Problemi comuni

| Problema | Cosa fare |
|---|---|
| Dopo il riavvio il telefono finisce in **Qualcomm 9008** | La catena non è partita. Tieni premuti accensione + volume giù per 10 s, poi volume su all'accensione (modalità flash) e ripristina EFIESP. |
| **fastboot non compare** (Windows) | Controlla il driver USB di Google in Gestione dispositivi: il telefono deve risultare *Android Bootloader Interface*. |
| Lo schermo mostra un punto esclamativo o *Cannot load this LK image* | Annota il messaggio, ripristina EFIESP e apri una segnalazione con i log. |
| **Due letture diverse** durante il backup | Cavo o porta instabili: cambiali (evita gli hub) e ripeti il backup. |
| **Partizioni ancora montate** | Chiudi le finestre di Esplora risorse/file manager che mostrano i dischi del telefono. |
| Linux: manca **hivex** | Installa il pacchetto della [sezione 3](#linux). |
| La finestra non si apre | Apri l'indirizzo scritto nel terminale, oppure avvia con `--text`. |
| Avviato senza permessi di amministratore | Backup e installazione sono disattivati: riavvia l'installer e accetta la richiesta. |

I log di ogni sessione sono in `work/logs/`: allegali alle segnalazioni, dopo aver controllato che
non contengano dati che vuoi tenere privati.

## 11. File e opzioni

Tutto quello che l'installer salva finisce in `work/` accanto all'installer:

| Cartella | Contenuto |
|---|---|
| `work/backups/` | backup del telefono e di EFIESP |
| `work/private/` | firmware estratto da Windows |
| `work/logs/` | log delle sessioni, di lk1st e degli avvii |
| `work/state.json` | avanzamento, lingua e colore |

Backup e firmware contengono dati personali e file Nokia/Microsoft: **non pubblicarli**.

| Opzione | Significato |
|---|---|
| `--mode full` | avvia l'installazione completa senza menu |
| `--lang en\|it` | lingua dell'interfaccia (predefinito inglese, o l'ultima scelta) |
| `--text` | interfaccia da terminale, per SSH o PC senza browser |
| `--text --action <passo>` | esegue un solo passo ed esce (`backup`, `chain`, `verify`, `boot`, `diag`…) |
| `--work <cartella>` | cartella dati (predefinita `work/` accanto all'installer) |
| `--no-browser` | scrive solo l'indirizzo della finestra |
| `--no-elevate` | non chiede i permessi di amministratore (solo passi fastboot) |

Esempio: `installer.bat --lang it` oppure `./installer.sh --text --mode full`.
