# Cost Control Guide

## GCP Free Tier Limits (per billing account, monthly)

### Cloud Run
| Resource | Free Allowance |
|----------|---------------|
| CPU | 180,000 vCPU-seconds |
| Memory | 360,000 GiB-seconds |
| Requests | 2,000,000 |
| Egress | 1 GB (North America) |

> **Instance-based billing** (`--no-cpu-throttling`): CPU is billed for the
> entire instance lifetime. With `--min-instances=0`, idle instances terminate
> after ~15 minutes.
>
> At 1 vCPU, the free tier covers **~50 hours** of active instance time/month.

### Firestore
| Resource | Free Allowance |
|----------|---------------|
| Storage | 1 GiB |
| Reads | 50,000/day |
| Writes | 20,000/day |
| Deletes | 20,000/day |
| Egress | 10 GiB/month |

### Firebase Hosting
| Resource | Free Allowance |
|----------|---------------|
| Storage | 1 GB |
| Transfer | 10 GB/month |

### Secret Manager
| Resource | Free Allowance |
|----------|---------------|
| Active versions | 6 |
| Access operations | 10,000/month |

### Cloud Build
| Resource | Free Allowance |
|----------|---------------|
| Build minutes | 120 min/day |

---

## Current Deployment Settings

```
Service:         song-shake-api
Region:          asia-southeast2
CPU throttling:  OFF (required for background enrichment jobs)
Min instances:   0 (auto-terminate when idle)
Max instances:   1 (prevents parallel cost)
Memory:          512Mi (minimum for CPU always allocated)
Timeout:         3600s (1 hour, for long enrichment jobs)
```

### Why `--no-cpu-throttling`?

Enrichment jobs run as `FastAPI.BackgroundTasks` inside the Cloud Run container.
With CPU throttling, CPU drops to ~5% after the HTTP response, which would stall
or kill hour-long enrichment jobs. The `--no-cpu-throttling` flag keeps CPU
allocated for the full instance lifetime.

---

## Budget Alert

A 16,000 IDR/month (~$1 USD) budget is created automatically by `deploy.sh`. Email alerts fire at:
- **50%** (8,000 IDR)
- **90%** (14,400 IDR)
- **100%** (16,000 IDR)

These are **notifications only** — they don't auto-disable billing.

---

## Monitoring Commands

```bash
# Check current billing
gcloud billing projects describe songshake999

# List budgets
gcloud billing budgets list --billing-account=015067-7C1A56-0A678B

# Check Cloud Run metrics (last 7 days)
gcloud run services describe song-shake-api \
  --region=asia-southeast2 \
  --format="yaml(status)"

# View Firestore usage
# Console: https://console.cloud.google.com/firestore/databases?project=songshake999

# View billing report
# Console: https://console.cloud.google.com/billing/015067-7C1A56-0A678B/reports?project=songshake999
```
