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

        VisualElement productList, stockList, interlockList, slotList;
        Label qtyValue, qtyMax, qtyEta, startReason, jobSummary, productName, productMeta, productSlotCount;
        Button start, qtyMinus, qtyPlus;
        bool cached;
        string interlockSignature;
        Product[] products = Array.Empty<Product>();
        ProductDetail selectedProduct;
        Requirement[] requirements = Array.Empty<Requirement>();
        string apiError;

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
            productSlotCount.text = $"product_slots {selectedProduct.slots?.Length ?? 0}";
        }

        void BuildSlots()
        {
            if (selectedProduct?.slots == null || selectedProduct.slots.Length == 0)
            {
                FR5EmptyState.Fill(slotList, selectedProduct == null ? "제품을 선택하세요" : "product_slots 조회 결과 없음", 160f);
                return;
            }

            slotList.Clear();
            foreach (Slot slot in selectedProduct.slots)
            {
                var label = new Label($"{slot.slot_code} · {slot.part_name} ({slot.part_id})");
                label.AddToClassList("chip");
                label.style.marginRight = 8;
                label.style.marginBottom = 8;
                slotList.Add(label);
            }
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
                ApplyStartState(linked, idle);
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

            ApplyStartState(linked, idle);
        }

        void ApplyStartState(bool linked, bool idle)
        {
            bool runnable = uiMaster == null || uiMaster.IsSimulated;
            bool all = linked && idle && runnable;
            start?.SetEnabled(all);
            if (startReason != null)
                startReason.text = all
                    ? "고정 레시피 mock-r1 · 수량 1 로 시작합니다 (제품·수량 선택 계약 없음)"
                    : FirstReason(linked, idle, runnable);
        }

        static string FirstReason(bool linked, bool idle, bool runnable)
        {
            if (!runnable) return "Real 자동 조립 미구현 — MOCK 에서만 요청할 수 있습니다 (API.md 2절)";
            if (!linked) return "ROS 미연결 — 상태 수신이 없습니다";
            if (!idle) return "이미 실행 중인 작업이 있습니다 (동시 1건)";
            return "";
        }

        void OnStart()
        {
            ScenarioRunnerSafeRun();
        }

        void ScenarioRunnerSafeRun()
        {
            var scenario = uiMaster != null ? uiMaster.Scenario : null;
            if (scenario == null)
            {
                if (startReason != null) startReason.text = "Scenario 미연결";
                return;
            }
            scenario.Run();
        }
    }
}
