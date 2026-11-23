# P2-09/P2-10 — Kiểm thử workload FastAPI

Chỉ chạy các bước cluster sau khi được duyệt và có handover Harbor, K3s, RDS và Ingress. Dùng đúng kubeconfig, context, namespace, digest và tên Migration Job của release. Xem quy trình [render, bootstrap và áp dụng](../../deploy/phase2/README.md). Các lệnh sau chạy từ gốc repo trong shell POSIX. Lưu bằng chứng đã che dữ liệu nhạy cảm.

## 1. Migration, node và image pull

```sh
JOB="song-migrate-$RELEASE_ID"
kubectl --context "$KUBE_CONTEXT" get nodes -l "$WORKER_LABEL" -o wide
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" get job "$JOB"
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" get pods -l "job-name=$JOB" -o wide
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" logs "job/$JOB"
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" get pods -l 'app.kubernetes.io/name=song-management,app.kubernetes.io/component=api' -o wide
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" describe pod "$API_POD"
```

Xác nhận Job `Complete=True`, container migrator exit `0`, Deployment available, API Pod `Running` và `Ready`. Đối chiếu tên node thật của Job Pod và API Pod với Worker đã duyệt. Với từng pod, lưu image ref theo digest, `imageID`, node và events pull liên quan. Đối chiếu Harbor HTTPS và CA trust với TV1. Registry manifest digest và runtime image/config ID có thể khác dạng. Giữ cả hai làm bằng chứng và đối chiếu theo artifact do registry trả. Một event image đã cache không chứng minh bản tải mới từ Harbor.

## 2. Database và đường HTTP

`verify_schema.py` chạy read-only qua role API trong pod. Kiểm tra tên DB đã bàn giao, kết nối TLS, `public.song` và Alembic revision. Script chỉ in kết quả tóm tắt. Role API cần quyền đọc `public.alembic_version`.

```sh
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" exec -i "$API_POD" -c api -- \
  python - "$EXPECTED_DB" "$EXPECTED_REVISION" < deploy/phase2/verify_schema.py
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" get service,ingress song-api
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" get endpointslice \
  -l kubernetes.io/service-name=song-api -o wide
python deploy/phase2/smoke.py health --url "$INGRESS_URL"
```

`EXPECTED_REVISION` là head của release, hiện là `750af730f01c`. Kiểm tra Ingress host/class/TLS, Service `ClusterIP` và EndpointSlice có API Pod Ready ở port 8000. `smoke.py` yêu cầu HTTPS cho Ingress và xác minh chứng chỉ. Nếu client cần private CA đã duyệt, thêm `--ca-bundle "$INGRESS_CA"` vào từng lệnh smoke. Health phải trả `200` cho hai probes.

## 3. CRUD và persistence

Các bước sau yêu cầu cho phép ghi dữ liệu thử nghiệm. Dùng `--allow-test-writes` với đúng Ingress đã xác nhận. Script tạo marker duy nhất, kiểm tra POST `201`, GET list/item `200`, PUT `200`, DELETE `204`, rồi GET `404`. Nếu một bước CRUD fail sau POST, dùng ID và marker đã in để xác minh và dọn đúng bản ghi thử khi được phép.

```sh
python deploy/phase2/smoke.py crud --url "$INGRESS_URL" --allow-test-writes
python deploy/phase2/smoke.py seed --url "$INGRESS_URL" --allow-test-writes > "$SMOKE_RECORD"
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" get pod "$API_POD" \
  -o jsonpath='{.metadata.uid}{"\n"}'
```

Lưu file sentinel ngoài Git. Khi được phép tái tạo API Pod trong namespace demo, xác nhận Pod cũ và mới có UID khác nhau, Pod mới Ready và vẫn nằm trên Worker. Có thể dùng `kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" rollout restart deployment/song-api` và chờ `rollout status` trong lần thử đã duyệt. Giữ nguyên DB. Khi Pod mới Ready, truy vấn lại chính xác bản ghi qua Ingress:

```sh
python deploy/phase2/smoke.py check --url "$INGRESS_URL" --record "$SMOKE_RECORD"
# Sau khi lưu bằng chứng, dọn sentinel nếu đã được duyệt.
python deploy/phase2/smoke.py check --url "$INGRESS_URL" --record "$SMOKE_RECORD" \
  --cleanup --allow-test-writes
```

Chỉ thử readiness `503` khi mất DB trong môi trường kiểm soát riêng. Giữ liveness `200`, lưu status và response đã che thông tin nhạy cảm. Không ngắt RDS dùng chung để chạy kiểm thử.

## Bằng chứng cần lưu

| Mục | Bằng chứng runtime |
| --- | --- |
| A08 và A10 | Kết quả TLS/SAN, tag và registry digest, push/pull, node Worker và pull events. |
| A09 (TV1) | Hai node Ready và cấu hình Ingress/ServiceLB, SG chứng minh Worker không có inbound public. |
| A11 | Job status/exit, Pod node, revision, bảng `song` và kết nối TLS. |
| A12 | Rollout/EndpointSlice/Ingress, probe và trạng thái CRUD. |
| A13 | Pod UID trước/sau và bản ghi sentinel giữ nguyên, dọn đúng bản ghi thử sau khi lưu bằng chứng. |

Kết quả local được đối chiếu riêng trong [báo cáo TV2](../../REPORT_PHASE2_TV2.md).
