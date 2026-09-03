// 역할: RUN · 작업 요청 페이지(FR5Request.uxml)의 폼 로직과 실행 인터록을 담당한다.
//
//   실연결 : 모드 · 로봇 상태 · 링크 · 인터록 판정 · START(Scenario.Run)
//   미연결 : 제품 목록 · 재고 · 슬롯 구성 · 예상 소요 — 값을 지어내지 않고
//            FR5EmptyState 로 필요한 조회 이름을 적는다  [TODO(API)]
//
// API.md 4.3 의 Mock MVP 는 고정 레시피 · 수량 1 · 동시 1건이다. 제품/수량을 goal 에
// 실어 보내는 계약이 없으므로, 지금 START 는 Scenario.Run() 만 호출한다.

using System;
using System.Collections;
using System.Collections.Generic;
using MainUnity.Runtime.Robot;
using MainUnity.Runtime.Robot.Assembly;
using MainUnity.Runtime.Robot.Status;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UIElements;

namespace MainUnity.UI
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(UIDocument))]
    public sealed class FR5RequestBinder : MonoBehaviour
    {
        [Serializable] sealed class ProductListResponse { public Product[] data; }
        [Serializable] sealed class ProductResponse { public ProductDetail data; }
        [Serializable] sealed class RequirementListResponse { public Requirement[] data; }

        [Serializable] sealed class Product
        {
            public int product_id;
            public string product_code;
            public string product_name;
            public string product_version;
            public int buildable_quantity;
        }

        [Serializable] sealed class ProductDetail
        {
            public int product_id;
            public string product_code;
            public string product_name;
            public string product_version;
            public Slot[] slots;
        }

        [Serializable] sealed class Slot
        {
            public string slot_code;
            public string part_id;
            public string part_name;
        }

        [Serializable] sealed class Requirement
        {
            public string part_id;
            public string part_name;
            public int required_quantity;
            public int stock_quantity;
            public int shortage_quantity;
        }

        [Header("데이터 소스")]
        [SerializeField] UIMaster uiMaster;
        [SerializeField] RobotMaster robotMaster;
        [SerializeField] RobotStatusManager statusManager;
        [SerializeField] string mainServerBaseUrl = "http://127.0.0.1:8000";

        [Header("요청")]
        [Tooltip("API.md 4.3 Mock MVP 는 수량 1 고정입니다. 계약이 생기면 상한이 재고로 바뀝니다.")]
        [SerializeField] int quantity = 1;

        [Header("완성체 미리보기")]
        [Tooltip("기판을 비추는 카메라의 RenderTexture 입니다. 비우면 미리보기 자리에 연결 없음을 적습니다.")]
        [SerializeField] RenderTexture productPreview;

        VisualElement productList, stockList, interlockList, slotList, previewEmpty;
        Image previewImage;
        Label qtyValue, qtyMax, qtyEta, startReason, jobSummary, productName, productMeta, productSlotCount,
              previewSource, previewDesc;
        Button start, qtyMinus, qtyPlus;
        bool cached;
        string interlockSignature;
        Product[] products = Array.Empty<Product>();
        ProductDetail selectedProduct;
        Requirement[] requirements = Array.Empty<Requirement>();
        string apiError;
        bool startRequestInFlight;

        void OnEnable()
        {
            cached = false;
            products = Array.Empty<Product>();
            selectedProduct = null;
            requirements = Array.Empty<Requirement>();
            apiError = null;
        }

        void Update()
        {
            // UIDocument 는 활성화된 뒤에야 rootVisualElement 를 만든다.
            if (!cached) { Build(); if (!cached) return; }
            ResolveReferences();
            RefreshMode();
            RefreshInterlocks();
        }

        void ResolveReferences()
        {
            if (uiMaster == null) uiMaster = GetComponentInParent<UIMaster>();
            if (uiMaster == null) return;
            if (robotMaster == null) robotMaster = uiMaster.RobotMaster;
            if (statusManager == null) statusManager = uiMaster.StatusManager;
        }

        void Build()
        {
            VisualElement root = GetComponent<UIDocument>().rootVisualElement;
            if (root == null) return;

            productSlotCount = root.Q<Label>("product-slot-count");
            FR5EmptyState.Detail(productSlotCount, "product_slots 조회 중");
            MarkRecipeUnverified(root);

            productList = root.Q<VisualElement>("product-list");
            stockList = root.Q<VisualElement>("stock-list");
            interlockList = root.Q<VisualElement>("interlock-list");
            slotList = root.Q<VisualElement>("slot-list");
            previewImage = root.Q<Image>("product-preview");
            previewEmpty = root.Q<VisualElement>("product-preview-empty");
            previewSource = root.Q<Label>("preview-source");
            previewDesc = root.Q<Label>("product-preview-desc");
            qtyValue = root.Q<Label>("qty-value");
            qtyMax = root.Q<Label>("qty-max");
            qtyEta = root.Q<Label>("qty-eta");
            startReason = root.Q<Label>("start-reason");
            jobSummary = root.Q<Label>("job-id");
            productName = root.Q<Label>("product-name");
            productMeta = root.Q<Label>("product-meta");
            start = root.Q<Button>("start-button");

            if (start != null) start.clicked += OnStart;
            qtyMinus = root.Q<Button>("qty-minus");
            qtyPlus = root.Q<Button>("qty-plus");
            qtyMinus?.SetEnabled(false);
            qtyPlus?.SetEnabled(false);

            BuildProducts();
            BuildSlots();
            BuildStock();
            RefreshPreview();
            SetQuantity(quantity);
            cached = true;
            StartCoroutine(LoadProducts());
        }

        static void MarkRecipeUnverified(VisualElement root)
        {
            VisualElement chip = root.Q<VisualElement>("recipe-match-chip");
            chip?.EnableInClassList("chip--good", false);
            Label text = chip?.Q<Label>();
            if (text != null) text.text = "노드가 판정";
        }

        void BuildProducts()
        {
            if (!string.IsNullOrEmpty(apiError))
            {
                FR5EmptyState.Fill(productList, apiError, 180f);
                RefreshProductHeader();
                return;
            }

            if (products == null || products.Length == 0)
            {
                FR5EmptyState.Fill(productList, "products 조회 결과 없음", 180f);
                RefreshProductHeader();
                return;
            }

            productList.Clear();
            foreach (Product product in products)
            {
                var button = new Button(() => SelectProduct(product))
                {
                    text = $"{product.product_name} · {product.product_code} · {product.product_version} · 가능 {product.buildable_quantity}"
                };
                button.AddToClassList("btn");
                button.style.height = 42;
                button.style.marginBottom = 6;
                productList.Add(button);
            }
            RefreshProductHeader();
        }

        void RefreshProductHeader()
        {
            if (selectedProduct == null)
            {
                FR5EmptyState.Missing(productName);
                FR5EmptyState.Detail(productMeta, string.IsNullOrEmpty(apiError) ? "제품을 선택하세요" : apiError);
                FR5EmptyState.Detail(productSlotCount, selectedProduct == null ? "product_slots 조회 대기" : "");
                return;
            }

            FR5EmptyState.Present(productName, selectedProduct.product_name);
            productMeta.text = $"{selectedProduct.product_code} · {selectedProduct.product_version}";
            int slots = selectedProduct.slots?.Length ?? 0;
            int types = selectedProduct.slots == null ? 0 : GroupByPart(selectedProduct.slots).Count;
            productSlotCount.text = $"product_slots {slots} · {types} 부품";
        }

        // ─────────────────────── 필요 부품 ───────────────────────
        //
        // 타일 하나 = 부품 타입 하나다. 슬롯 하나가 아니다.
        // 목 완성체만 해도 product_slots 가 25행이라 슬롯마다 칸을 만들면 620px 패널이
        // 글자벽이 된다. 게다가 우측 재고표는 requirements 를 부품 단위로 세는데 좌측만
        // 슬롯 단위면 같은 화면에서 같은 것을 두 단위로 세게 된다. 여기서 접어 맞춘다.

        /// <summary>부품 타입 하나와 그 개수다. 순서는 product_slots 가 준 순서를 지킨다.</summary>
        sealed class PartGroup
        {
            public string PartId;
            public string PartName;
            public int Count;
        }

        void BuildSlots()
        {
            if (selectedProduct?.slots == null || selectedProduct.slots.Length == 0)
            {
                FR5EmptyState.Fill(slotList, selectedProduct == null ? "제품을 선택하세요" : "product_slots 조회 결과 없음", 160f);
                return;
            }

            slotList.Clear();
            foreach (PartGroup group in GroupByPart(selectedProduct.slots))
                slotList.Add(PartTile(group));
        }

        /// <summary>
        /// 슬롯을 부품 타입으로 접는다. Dictionary 만 쓰면 열거 순서가 흐트러져 화면에서
        /// 부품 차례가 조회할 때마다 달라지므로, 등장 순서는 리스트가 따로 지킨다.
        /// </summary>
        static List<PartGroup> GroupByPart(Slot[] slots)
        {
            var order = new List<PartGroup>();
            var index = new Dictionary<string, PartGroup>(StringComparer.OrdinalIgnoreCase);
            foreach (Slot slot in slots)
            {
                string partId = string.IsNullOrEmpty(slot.part_id) ? "—" : slot.part_id;
                if (!index.TryGetValue(partId, out PartGroup group))
                {
                    group = new PartGroup { PartId = partId, PartName = slot.part_name };
                    index[partId] = group;
                    order.Add(group);
                }
                group.Count++;
            }
            return order;
        }

        /// <summary>
        /// 타일 하나다. 그림은 USS 가 part_id 로 고른다 (FR5Theme.uss 의 .parttile__icon--*).
        /// 여기서 Sprite 를 직접 잡지 않는 이유는, 잡는 순간 부품 목록이 코드로 들어와
        /// 부품이 늘 때마다 이 파일을 고쳐야 하기 때문이다. part_id 는 DB 의 자유 텍스트라
        /// 언제든 새 값이 온다. 규칙이 없는 값은 그림 없이 이니셜만 남는다.
        /// </summary>
        static VisualElement PartTile(PartGroup group)
        {
            var tile = new VisualElement();
            tile.AddToClassList("parttile");
            // 정식 부품명은 "SK hynix HBM3E 12-Hi 36GB" 처럼 길어 176px 타일에 들어가지
            // 않는다. 타일에는 part_id 만 적고 전체 이름은 tooltip 으로 넘긴다.
            tile.tooltip = string.IsNullOrEmpty(group.PartName) ? group.PartId : group.PartName;

            var icon = new VisualElement();
            icon.AddToClassList("parttile__icon");
            icon.AddToClassList("parttile__icon--" + group.PartId.ToLowerInvariant());

            var fallback = new Label(Initials(group.PartId));
            fallback.AddToClassList("parttile__fallback");
            icon.Add(fallback);
            tile.Add(icon);

            var line = new VisualElement();
            line.AddToClassList("parttile__line");

            var name = new Label(group.PartId.ToUpperInvariant());
            name.AddToClassList("parttile__name");
            line.Add(name);

            var count = new Label("×" + group.Count);
            count.AddToClassList("parttile__count");
            line.Add(count);

            tile.Add(line);
            return tile;
        }

        /// <summary>그림이 없을 때 남는 글자다. 세 자를 넘기면 64px 칸을 벗어난다.</summary>
        static string Initials(string partId)
        {
            if (string.IsNullOrEmpty(partId)) return "—";
            return partId.Length <= 3
                ? partId.ToUpperInvariant()
                : partId.Substring(0, 3).ToUpperInvariant();
        }

        /// <summary>
        /// 완성체 그림이다. 제품마다 PNG 를 두지 않는 이유는 UXML 주석에 적었다 —
        /// production.products 에 이미지 경로 컬럼이 없어서 파일을 쓰면 매핑을 화면이
        /// 떠안는다. 카메라가 없으면 그림을 지어내지 않고 없다고 적는다.
        /// </summary>
        void RefreshPreview()
        {
            bool ready = productPreview != null;

            if (previewImage != null)
            {
                previewImage.image = ready ? productPreview : null;
                previewImage.style.display = ready ? DisplayStyle.Flex : DisplayStyle.None;
            }
            if (previewEmpty != null)
                previewEmpty.style.display = ready ? DisplayStyle.None : DisplayStyle.Flex;

            FR5EmptyState.Detail(previewSource, ready
                ? $"{productPreview.width}×{productPreview.height}"
                : "카메라 미지정");
            if (!ready)
                FR5EmptyState.Detail(previewDesc, "기판을 비추는 카메라의 RenderTexture 를 바인더에 넣으세요");
        }

        void BuildStock()
        {
            if (requirements == null || requirements.Length == 0)
            {
                FR5EmptyState.Fill(stockList, selectedProduct == null ? "제품을 선택하세요" : "requirements 조회 결과 없음", 160f);
                return;
            }

            stockList.Clear();
            foreach (Requirement requirement in requirements)
            {
                var row = new VisualElement();
                row.AddToClassList("trow");
                AddCell(row, requirement.part_id, 280);
                AddCell(row, requirement.part_name, 220);
                AddCell(row, requirement.required_quantity.ToString(), 120);
                AddCell(row, requirement.stock_quantity.ToString(), 120);
                AddCell(row, requirement.shortage_quantity == 0 ? "가능" : $"부족 {requirement.shortage_quantity}", 160);
                stockList.Add(row);
            }
        }

        static void AddCell(VisualElement row, string text, float width)
        {
            var cell = new Label(text);
            cell.AddToClassList("tcell");
            cell.style.width = width;
            row.Add(cell);
        }

        void SetQuantity(int value)
        {
            quantity = Mathf.Max(1, value);
            if (qtyValue != null) qtyValue.text = quantity.ToString();
            FR5EmptyState.Detail(qtyMax, "수량 1 고정 (API.md 4.3)");
            FR5EmptyState.Dash(qtyEta);
            interlockSignature = null;
        }

        void SelectProduct(Product product)
        {
            selectedProduct = null;
            requirements = Array.Empty<Requirement>();
            apiError = null;
            BuildProducts();
            BuildSlots();
            BuildStock();
            StartCoroutine(LoadProduct(product.product_id));
        }

        IEnumerator LoadProducts()
        {
            yield return Get("/api/v1/products", json =>
            {
                products = JsonUtility.FromJson<ProductListResponse>(json)?.data ?? Array.Empty<Product>();
                BuildProducts();
                if (products.Length > 0) SelectProduct(products[0]);
            });
        }

        IEnumerator LoadProduct(int productId)
        {
            yield return Get($"/api/v1/products/{productId}", json =>
            {
                selectedProduct = JsonUtility.FromJson<ProductResponse>(json)?.data;
                RefreshProductHeader();
                BuildSlots();
                StartCoroutine(LoadRequirements(productId));
            });
        }

        IEnumerator LoadRequirements(int productId)
        {
            yield return Get($"/api/v1/products/{productId}/requirements?quantity={quantity}", json =>
            {
                requirements = JsonUtility.FromJson<RequirementListResponse>(json)?.data ?? Array.Empty<Requirement>();
                BuildStock();
            });
        }

        IEnumerator Get(string path, Action<string> onSuccess)
        {
            using var request = UnityWebRequest.Get(ApiUrl(path));
            request.timeout = 5;
            yield return request.SendWebRequest();
            if (request.result == UnityWebRequest.Result.Success)
            {
                try { onSuccess(request.downloadHandler.text); }
                catch (Exception) { SetApiError("MainServer 응답 형식 오류"); }
                yield break;
            }

            SetApiError($"MainServer 조회 실패 · {request.responseCode}");
        }

        void SetApiError(string message)
        {
            apiError = message;
            products = Array.Empty<Product>();
            selectedProduct = null;
            requirements = Array.Empty<Requirement>();
            BuildProducts();
            BuildSlots();
            BuildStock();
        }


        string ApiUrl(string path) => $"{mainServerBaseUrl.TrimEnd('/')}{path}";

        [ContextMenu("API/Self Check")]
        void ApiSelfCheck() => Debug.Assert(ApiUrl("/api/v1/products") == "http://127.0.0.1:8000/api/v1/products");

        void RefreshMode()
        {
            RobotRunState state = statusManager != null ? statusManager.State : RobotRunState.Disconnected;
            AssemblyProgressFrame progress = uiMaster != null ? uiMaster.AssemblyProgress?.Latest : null;
            bool active = state == RobotRunState.Running || (progress != null && !progress.IsTerminal);
            if (jobSummary != null)
                jobSummary.text = active ? "실행 중" : "활성 작업 없음";
        }

        void RefreshInterlocks()
        {
            if (interlockList == null) return;

            bool linked = statusManager != null && statusManager.Latest != null;
            RobotRunState state = statusManager != null ? statusManager.State : RobotRunState.Disconnected;
            AssemblyProgressFrame progress = uiMaster != null ? uiMaster.AssemblyProgress?.Latest : null;
            bool idle = state != RobotRunState.Running && (progress == null || progress.IsTerminal);
            bool mock = uiMaster == null || uiMaster.IsSimulated;

            var checks = new List<(string, bool)>
            {
                ("ROS-TCP 연결", linked),
                ("워치독 정상", state != RobotRunState.Disconnected),
                ("활성 작업 없음", idle),
                ("모드 = MOCK (Real 자동조립 미구현)", mock),
            };

            string signature = string.Concat(linked, idle, mock, state);
            if (signature == interlockSignature)
            {
                ApplyStartState(idle);
                return;
            }
            interlockSignature = signature;

            interlockList.Clear();
            foreach ((string name, bool ok) in checks)
            {
                var item = new VisualElement();
                item.AddToClassList("row");
                item.style.width = 340;
                item.style.height = 34;

                var dot = new VisualElement();
                dot.AddToClassList("dot");
                dot.AddToClassList(ok ? "dot--good" : "dot--bad");
                item.Add(dot);

                var label = new Label(name);
                label.style.marginLeft = 10;
                label.style.fontSize = 14;
                label.style.color = ok ? new Color(0.62f, 0.69f, 0.75f) : new Color(1f, 0.56f, 0.61f);
                item.Add(label);
                interlockList.Add(item);
            }

            var note = new Label("재고 · recipe_version 은 조립 노드가 판정한다 (Unity 조회 없음)");
            note.AddToClassList("muted");
            note.style.fontSize = 12;
            note.style.marginTop = 8;
            interlockList.Add(note);

            ApplyStartState(idle);
        }

        void ApplyStartState(bool idle)
        {
            start?.SetEnabled(idle && !startRequestInFlight);
            if (start != null)
                start.text = startRequestInFlight ? "RUNNING…" : "START";
            if (startReason != null)
                startReason.text = startRequestInFlight
                    ? "작업을 실행하고 있습니다. 운전 현황은 RUN 화면에서 확인할 수 있습니다."
                    : idle
                    ? "고정 레시피 assembly-r1 · 수량 1 로 시작합니다 (제품·수량 선택 계약 없음)"
                    : "이미 실행 중인 작업이 있습니다 (동시 1건)";
        }

        async void OnStart()
        {
            if (startRequestInFlight) return;

            var scenario = uiMaster != null ? uiMaster.Scenario : null;
            if (scenario == null)
            {
                if (startReason != null) startReason.text = "Scenario 미연결";
                return;
            }

            startRequestInFlight = true;
            ApplyStartState(false);
            try
            {
                await scenario.Run();
            }
            catch (Exception exception)
            {
                if (startReason != null) startReason.text = exception.Message;
                Debug.LogException(exception, this);
            }
            finally
            {
                startRequestInFlight = false;
            }
        }
    }
}
