# Lumia 1520 Android installer: user guide

[Italiano](GUIDA.md) · [README](../README.md)

This guide takes you from a Lumia 1520 running Windows 10 Mobile to a phone that starts
**lk1st** (the Android bootloader) from its own boot manager, step by step.

> **Experimental.** Today the installer prepares the boot chain and checks that lk1st answers in
> fastboot. Android itself cannot be installed yet: the Android partitions and the ROM (phase 2) will
> come once the partition layout is final. Windows stays on the phone and keeps working.

## Contents

1. [What you need](#1-what-you-need)
2. [Download](#2-download)
3. [Prepare the PC](#3-prepare-the-pc)
4. [Unlock the phone and switch it to mass storage](#4-unlock-the-phone-and-switch-it-to-mass-storage)
5. [Start the installer](#5-start-the-installer)
6. [Full install, step by step](#6-full-install-step-by-step)
7. [After the install](#7-after-the-install)
8. [Advanced tools](#8-advanced-tools)
9. [Going back](#9-going-back)
10. [Troubleshooting](#10-troubleshooting)
11. [Files and options](#11-files-and-options)

## 1. What you need

- A **Nokia Lumia 1520** (RM-937, RM-938 or RM-940) with Windows Phone 8.1 or Windows 10 Mobile.
- A **Windows 10/11 PC** for the unlock with [WPinternals](https://github.com/ReneLergner/WPinternals).
  The installer itself runs on that PC or on a **Linux** PC.
- A good USB cable (a bad one shows up as "two different reads" during the backup) and the phone
  charged above 50%.
- Free space on the PC: about 1 GB for the basic backup, plus the size of a compressed copy of the
  whole phone if you keep the full image (recommended, a few GB to tens of GB depending on how full
  the phone is).
- 30–90 minutes, most of it for the full backup.

## 2. Download

From the [releases page](https://github.com/giannoccarol/bandit-installer/releases) download the
package for your system and, optionally, `SHA256SUMS` to check it:

| System | File | Contains |
|---|---|---|
| Windows (64-bit) | `bandit-installer-<version>-windows.zip` | the installer and its own Python, nothing else to install |
| Linux | `bandit-installer-<version>-linux.tar.gz` | the installer; uses the system Python 3 |

Unpack it into a folder with enough free space: backups and logs go to `work\` inside that folder.
On Windows extract the whole zip first (right click → *Extract all*); do not start it from inside the
zip.

## 3. Prepare the PC

### Windows

1. Install the [Google USB driver](https://developer.android.com/studio/run/win-usb), so that Windows
   recognises the phone in fastboot.
2. Have **Edge** or **Chrome** installed (Edge is part of Windows): the installer opens in an app
   window of that browser.
3. `fastboot` and `adb` are not needed in advance: the installer offers to download Google's
   Platform Tools into its `tools\` folder.

### Linux

Install Python 3 (3.8 or newer), the hivex Python binding (to edit the BCD), util-linux and
NTFS support (for the firmware step):

```bash
sudo pacman -S python hivex util-linux ntfs-3g                      # Arch
sudo apt install python3 python3-hivex util-linux ntfs-3g           # Debian, Ubuntu
sudo dnf install python3 python3-hivex util-linux ntfs-3g           # Fedora
```

For the app window you need Chromium, Chrome, Brave or Edge; without them the default browser opens
a tab, and `--text` gives a terminal interface. `fastboot` and `adb` from your distribution work; if
they are missing the installer can download Google's copy.

## 4. Unlock the phone and switch it to mass storage

This part is done with WPinternals on Windows, outside this installer.

1. Follow the WPinternals instructions to **unlock the bootloader**.
2. In WPinternals choose **Switch to Mass Storage Mode**. The phone shows a USB symbol and its
   partitions appear on the PC.
3. A full backup of the phone at this point is a good idea (the installer can make one for you).

After the unlock you may move the cable to a Linux PC: the phone stays in mass storage mode until it
restarts.

## 5. Start the installer

| System | How |
|---|---|
| Windows | double-click `installer.bat` and accept the administrator prompt |
| Linux | `./installer.sh` in a terminal; it asks for your password through `sudo` |

Administrator (root) rights are needed to read and write the phone's disk. The installer then opens
its window, which shows:

- on the left, a coloured box with the **phone status** (not connected, mass storage, fastboot,
  flash mode…); click it to run a diagnostic;
- **Install**, with the three modes and the progress of the full install;
- **Advanced tools**, with each step on its own;
- **Settings**, for the language (English or Italian), the accent colour and the data folder.

The window talks to the installer through a local address (`127.0.0.1`) shown in the terminal. If no
window opens, copy that address into a browser. Closing the window does not stop the installer:
use **Settings → Quit**, or Ctrl+C in the terminal.

## 6. Full install, step by step

Connect the phone in mass storage mode and click **Start** on **Full install**. The installer goes
through these steps and remembers each one: if you stop, the next time it offers to skip what is done.

### 6.1 Platform Tools

If `fastboot` or `adb` are missing it asks to download Google's Platform Tools (about 7 MB).

### 6.2 Backup

It finds the phone's disk by its partition table and asks whether to make the **full compressed
image** too. Then it saves:

- the partition table (primary and backup GPT);
- every partition under 512 MiB (DPP, modem, UEFI, EFIESP…), read **twice** and compared;
- the full image, if chosen (20–60 minutes);
- a `SHA256SUMS` list of everything.

The backup contains personal and modem data (DPP, MODEM_FS*): keep it, and never publish it.

### 6.3 Firmware from Windows

It copies from the Windows partitions the firmware Android will need (ADSP, Wi-Fi, modem, Venus),
the audio and Wi-Fi calibration, the ACPI tables and the registry, and splits the `.mbn` files into
the `.mdt` + `.bNN` form Android loads. These are Nokia/Microsoft files: they stay on your PC.

### 6.4 Boot chain

This is the only step that writes to the phone, and only to the **EFIESP** partition.

1. It shows the current boot configuration (BCD).
2. It asks the **boot options**:
   - **lk1st**: the lk1st build to install (the verified one is preselected);
   - **Start Android at power-on**: on = lk1st starts by default; off = Windows starts and the
     Android entry stays in the menu;
   - **Volume down → the other system**: the volume down key at power-on starts the system that is
     not the default (instead of *Reset My Phone*);
   - **Android only**: for when Windows has already been removed;
   - **Menu timeout**: seconds the boot menu waits; 0 = no menu.
3. It backs up EFIESP (files and raw image), writes the new BCD **next to the backup**, reads it back
   and checks it: one new entry, the other entries unchanged, volume up still opens flash mode.
4. It shows the new BCD and asks you to type **INSTALL**.
5. It writes BootShim, lk1st and the BCD, and compares each file with the kit.

**Volume up at power-on always opens flash mode**: that is the way back with WPinternals, and the
installer refuses any configuration that would change it.

### 6.5 Restart and lk1st check

Restart the phone: leave mass storage mode in WPinternals, or hold **power + volume down** for about
10 seconds until it vibrates. The BootShim text appears, then the screen stays still: this lk1st does
not drive the display, so a still screen is expected.

The installer waits for fastboot and tells you what it sees on the way (Windows Phone boot manager,
fastboot, Qualcomm 9008…). When lk1st answers it saves `fastboot getvar all` and the lk1st log in
`work/logs/`. The progress list now shows all four steps done.

### 6.6 K1 test kernel (optional)

At the end it offers to boot **K1**, the first bandit kernel, in RAM (`fastboot boot`). Nothing is
written to the phone and the next restart goes back to lk1st. K1 has never been booted on a phone so
far: if you try it, keep the logs it collects.

## 7. After the install

| You do | The phone starts |
|---|---|
| power on (Android default) | lk1st in fastboot, still screen |
| power on with volume down (if chosen) | Windows 10 Mobile |
| power on with volume up | flash mode, for WPinternals |

With **Start Android at power-on** off, Windows starts as before and lk1st is in the boot menu.

## 8. Advanced tools

Each step of the full install can also be run on its own, plus a few tools for development:

| Tool | Phone mode | Writes to the phone |
|---|---|---|
| Backup, Firmware | mass storage | no |
| Boot chain | mass storage | EFIESP only, after a backup |
| Check lk1st | restart → fastboot | no |
| Boot in RAM | fastboot | no: `fastboot boot` of K1 or a `boot.img` |
| Previous boot log | fastboot | no: ram console and lk1st log after a hang |
| Write partition | fastboot | yes, Android partitions only (`boot`, `recovery`, `system`…) |
| Restore EFIESP | mass storage | yes, from a backup |
| Diagnostics | any | no |
| Platform Tools | — | no |

Every step that writes asks you to type a word first (`INSTALL`, `WRITE`, `RESTORE`).

## 9. Going back

- **From the installer**: put the phone in mass storage mode (volume up at power-on, then
  WPinternals) and run **Advanced tools → Restore EFIESP**. Pick the backup made before the boot
  chain. On Windows the files are put back; on Linux you can also write back the whole partition image.
- **By hand on Linux**, with the partition unmounted and the device name checked twice:
  `dd if=work/backups/efiesp-<date>/efiesp-partition.img of=/dev/sdX<n> bs=1M conv=fsync`.
- **By hand on Windows**: write `efiesp-partition.img` to EFIESP with Win32DiskImager.
- **If the phone does not start at all**: volume up at power-on (flash mode), then WPinternals or the
  Windows Device Recovery Tool.

## 10. Troubleshooting

| Problem | What to do |
|---|---|
| The phone ends in **Qualcomm 9008** after the restart | The chain did not start. Hold power + volume down for 10 s, then volume up at power-on (flash mode) and restore EFIESP. |
| **fastboot does not appear** (Windows) | Check the Google USB driver in Device Manager: the phone must show as *Android Bootloader Interface*. |
| The screen shows an exclamation mark or *Cannot load this LK image* | Note the message, restore EFIESP and open an issue with the logs. |
| **Two different reads** during the backup | Unstable cable or port: change them (avoid hubs) and run the backup again. |
| **Partitions still mounted** | Close Explorer/file manager windows showing the phone's drives. |
| Linux: **hivex** missing | Install the package from [section 3](#linux). |
| No window opens | Open the address printed in the terminal, or start with `--text`. |
| Started without administrator rights | Backup and install are disabled; start the installer again and accept the prompt. |

The logs of each session are in `work/logs/`: attach them to any report, after checking they contain
no data you want to keep private.

## 11. Files and options

Everything the installer saves goes to `work/` next to it:

| Folder | Contents |
|---|---|
| `work/backups/` | phone and EFIESP backups |
| `work/private/` | firmware extracted from Windows |
| `work/logs/` | session logs, lk1st and boot logs |
| `work/state.json` | progress, language and colour |

Backups and firmware contain personal data and Nokia/Microsoft files: **do not publish them**.

| Option | Meaning |
|---|---|
| `--mode full` | start the full install without the menu |
| `--lang en\|it` | interface language (default English, or the last one chosen) |
| `--text` | terminal interface, for SSH or machines without a browser |
| `--text --action <task>` | run one task and exit (`backup`, `chain`, `verify`, `boot`, `diag`…) |
| `--work <folder>` | data folder (default `work/` next to the installer) |
| `--no-browser` | only print the address of the window |
| `--no-elevate` | do not ask for administrator rights (fastboot tasks only) |

Example: `installer.bat --lang it` or `./installer.sh --text --mode full`.
