# Uninstall DJAMP PRO (macOS)

## 1) Stop app and helper

- Quit DJAMP PRO from the app UI.
- If helper is installed, uninstall it from Settings.

## 2) Remove local data

```bash
rm -rf "${HOME}/Library/Application Support/DJAMP PRO"
```

## 3) Remove local CA trust (optional)

```bash
sudo security delete-certificate -c "DJAMP PRO Root CA" /Library/Keychains/System.keychain || true
sudo security delete-certificate -c "DJAMP PRO Root CA" ~/Library/Keychains/login.keychain-db || true
```

## 4) Remove managed hosts block (optional)

Edit `/etc/hosts` and remove lines between:

- `# BEGIN DJAMP PRO MANAGED`
- `# END DJAMP PRO MANAGED`
