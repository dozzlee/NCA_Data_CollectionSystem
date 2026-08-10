# Development setup

Start the services, apply the committed migrations, and explicitly load the demo:

```sh
docker compose up -d
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py seed_demo
```

`seed_demo` is idempotent and refuses to run when Django `DEBUG` is disabled. It creates the
MTN and Vodafone Data Entry/Approver accounts documented for acceptance testing, plus an active
MNO monthly demonstration form for both providers.

Run verification with:

```sh
docker compose exec backend python manage.py test
docker compose exec frontend npm run build
```
