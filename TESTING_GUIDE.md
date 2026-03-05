# DJAMP PRO - Testing Guide (`certs_test`)

This guide validates a sample Django project with local domain + HTTPS on macOS.

## 1) Prepare certificates

If needed, trust the local DJAMP PRO root CA:

```bash
sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain ~/.djamp/certs/ca/djamp-pro-root-ca.crt
```

## 2) Add local host entry

```bash
sudo sh -c 'echo "127.0.0.1    certs_test.test" >> /etc/hosts'
```

## 3) Start the sample Django app manually

```bash
cd test_project/certs_test
python3 manage.py runserver 0.0.0.0:8001
```

## 4) Validate app access

- HTTP: `http://certs_test.test:8001`
- HTTPS: `https://certs_test.test:8001`

## 5) Useful Django checks

```bash
cd test_project/certs_test
python3 manage.py check
python3 manage.py test
```

## 6) Quick diagnostics

```bash
lsof -i :8001
cat /etc/hosts | grep certs_test
curl -I http://127.0.0.1:8001/
```

## Notes

- DJAMP PRO is for local development only.
- This file documents manual validation of the sample project.
- Product-level workflows are documented in `README.md` and `docs/`.
