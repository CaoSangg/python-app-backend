# Workload bootstrap Phase 2

`deploy/phase2/` là vị trí tạm trong backend vì workspace chưa có `k8s-gitops-manifests`. Các template dùng để render offline và review trước khi áp dụng. Xem [bằng chứng baseline](../../docs/phase2/00-baseline.md) và [kịch bản nghiệm thu](../../docs/phase2/09-app-smoke.md).

## Image và dữ liệu đầu vào

- Build target `runtime` từ source SHA đã chốt, context `project/` và platform Worker đã xác nhận. Kế hoạch hiện ghi Ubuntu amd64 trên `t3.large`. [Cấu hình EC2 T3](https://docs.aws.amazon.com/ec2/latest/instancetypes/gp.html)
- TV1 bàn giao Harbor hostname/SAN, CA đáng tin cậy, project private, tài khoản publish và quyền pull hạn chế. Dùng cùng hostname được xác nhận ở client và trên Worker. Kiểm tra Harbor ping bằng `curl --fail --cacert "$HARBOR_CA" "https://$HARBOR_HOST/api/v2.0/ping"`. TV1 quản lý trust của K3s/containerd.
- Sau khi được phép push, dùng Docker credential store hoặc đăng nhập qua `--password-stdin` từ nguồn secret đã duyệt. Gắn tag `<Harbor>/<project>/song-management:<source-sha>`, đảm bảo tag không ghi đè, push, rồi lấy `Digest` từ `docker buildx imagetools inspect "$IMAGE_REPO:$SOURCE_SHA"`. Kiểm tra bằng `docker pull "$IMAGE_REPO@$REGISTRY_DIGEST"`. Lưu SHA, tag và digest do registry trả. Local image ID chỉ dùng để đối chiếu build. [Kubernetes image digests](https://kubernetes.io/docs/concepts/containers/images/#image-names)
- Chốt namespace, ingress class, hostname, TLS Secret và label thật của Worker. Đối chiếu bằng `kubectl --context "$KUBE_CONTEXT" get nodes -l "$WORKER_LABEL" -o wide` sau khi được cấp quyền. Label phải chỉ khớp Worker được duyệt. Xác nhận node amd64, Ready và yêu cầu tolerations nếu cụm thực có taint.

Sau khi push được phê duyệt, dùng image local từ baseline đã xác minh:

```sh
docker tag "song-management:$SOURCE_SHA" "$IMAGE_REPO:$SOURCE_SHA"
docker push "$IMAGE_REPO:$SOURCE_SHA"
docker buildx imagetools inspect "$IMAGE_REPO:$SOURCE_SHA"
```

Gán `REGISTRY_DIGEST` từ kết quả inspect, xác minh lại bằng pull theo digest rồi dùng chính digest đó để render.

## Render offline

Chạy từ gốc repo với Python 3.12 và thư mục output mới bên ngoài repo. Mọi biến trong lệnh lấy từ handover đã duyệt, riêng `RELEASE_ID` là ID duy nhất cho lần chạy migration.

- `IMAGE_REPO` dùng FQDN của Harbor, có thể kèm port từ `1` đến `65535`. Ví dụ offline là `harbor.example.invalid:8443/lab/song-management`. `REGISTRY_DIGEST` phải có dạng `sha256:` theo sau bởi 64 ký tự hex thường.
- `WORKER_LABEL` dùng dạng `key=value` với value khác rỗng. Có thể dùng key đầy đủ như `node-role.kubernetes.io/worker=worker` nếu nó khớp label thật của Worker.
- `RELEASE_ID` là nhãn DNS chữ thường, dài tối đa 50 ký tự. `INGRESS_HOST` là FQDN, bỏ scheme, port và path.

```sh
python deploy/phase2/render.py --output "$RENDER_DIR" --namespace "$NAMESPACE" \
  --release-id "$RELEASE_ID" --image "$IMAGE_REPO@$REGISTRY_DIGEST" \
  --worker-label "$WORKER_LABEL" --ingress-class "$INGRESS_CLASS" \
  --host "$INGRESS_HOST" --tls-secret "$INGRESS_TLS_SECRET"
kubeconform -strict -summary -kubernetes-version "$K8S_VERSION" "$RENDER_DIR"
```

Chạy test hồi quy của renderer từ gốc repo trong virtualenv đã cài Pytest:

```sh
python -m pytest deploy/phase2/tests/test_render.py -p no:cacheprovider
```

| Giai đoạn | YAML render | Nội dung |
| --- | --- | --- |
| Namespace | `00-namespace.yaml` | Namespace được chốt khi render |
| Migration | `10-migration.yaml` | Job `song-migrate-<release-id>`, `alembic upgrade head`, Worker, image theo digest |
| API | `20-workload.yaml` | Deployment `song-api`, ClusterIP Service port 80 tới container port 8000, Ingress HTTPS qua controller bàn giao |

Job và API dùng cùng digest và Worker selector. Cả hai chạy UID/GID `10001:10001`, root filesystem chỉ đọc, drop capabilities, tắt service account token mount và có resource requests/limits cho Lab. Readiness cho phép ba giây để ứng dụng thực hiện timeout DB hai giây. Giá trị resources và scheduler cần kiểm chứng trên cụm được bàn giao.

## Bootstrap cấu hình và secrets sau khi được duyệt

| Đối tượng trong namespace workload | Dữ liệu và nguồn |
| --- | --- |
| `harbor-pull` | Secret loại `kubernetes.io/dockerconfigjson` từ Docker config đã provision và giới hạn pull. Dùng file riêng bên ngoài Git. |
| `song-db-migrator` | Secret key `DATABASE_URL` từ file runtime chỉ chứa DSN của role Alembic. Role cần tạo/cập nhật schema đích. |
| `song-db-app` | Secret key `DATABASE_URL` của role CRUD, cùng endpoint, port và database với migrator. Cần quyền sequence/CRUD và đọc `public.alembic_version` cho bước nghiệm thu. |
| `rds-ca` | ConfigMap key `ca-bundle.pem` từ RDS CA bundle đúng region. Job và API mount chỉ đọc. |
| Secret TLS do TV1 bàn giao | Cert/key đúng hostname Ingress. Controller và TLS termination cần được TV1 xác nhận. |

`DATABASE_URL` dùng `postgresql+asyncpg://` với hostname RDS thật và mật khẩu percent-encoded. Cả hai workload đặt `PGSSLMODE=verify-full`, `PGSSLROOTCERT=/etc/rds-ca/ca-bundle.pem`. Dùng DSN không có SSL override hoặc chỉ rõ `?ssl=verify-full`. `asyncpg` nhận CA qua biến môi trường. Không ghi DSN, token, kubeconfig hoặc manifest Secret đã render vào Git. [RDS PostgreSQL TLS](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.SSL.html)

Sau khi có phê duyệt và đúng context, tạo namespace và nhờ hệ thống cấp secrets được duyệt cung cấp objects trên. Nếu nhóm dùng file ngắn hạn để bootstrap, ví dụ dưới đây tránh đưa giá trị secret vào dòng lệnh. File DSN phải chứa đúng giá trị, không thêm newline. Không dùng bước này để thay secret đã tồn tại.

```sh
kubectl --context "$KUBE_CONTEXT" apply -f "$RENDER_DIR/00-namespace.yaml"
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" create secret generic harbor-pull \
  --type=kubernetes.io/dockerconfigjson --from-file=.dockerconfigjson="$HARBOR_PULL_CONFIG"
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" create secret generic song-db-migrator \
  --from-file=DATABASE_URL="$MIGRATOR_DSN_FILE"
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" create secret generic song-db-app \
  --from-file=DATABASE_URL="$APP_DSN_FILE"
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" create configmap rds-ca \
  --from-file=ca-bundle.pem="$RDS_CA_BUNDLE"
```

## Migration là điều kiện rollout

Trước khi chạy, xác minh RDS private đã available, SG chỉ cho Worker TCP 5432, cả hai DSN chỉ cùng DB đã duyệt, Secrets/ConfigMap có sẵn và ingress/TLS đã chốt. Áp dụng theo từng file. Dùng `create` với Job ID mới để lượt migration không tái sử dụng điều kiện `Complete` từ Job cũ. [kubectl wait](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_wait/)

```sh
set -eu
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" create -f "$RENDER_DIR/10-migration.yaml"
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" wait --for=condition=complete \
  --timeout=620s -f "$RENDER_DIR/10-migration.yaml"
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" apply -f "$RENDER_DIR/20-workload.yaml"
kubectl --context "$KUBE_CONTEXT" -n "$NAMESPACE" rollout status deployment/song-api --timeout=180s
```

Nếu Job fail hoặc timeout, dừng trước bước apply workload. Kiểm tra Job/Pod events và log đã loại thông tin nhạy cảm. Giữ Job để thu bằng chứng. Khi cần thử lại sau khi xử lý nguyên nhân, dùng release ID mới. Không tự chạy downgrade để rollback app.
