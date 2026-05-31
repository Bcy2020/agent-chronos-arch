# Attention Separation Experiment Report

- **Model:** deepseek-v4-flash
- **Temperature:** 0.3
- **Trials:** 5
- **Date:** 2026-05-25

---

## Methodology

Two-phase decomposition:
- **Phase 1**: Structural decomposition only — children with name, purpose, behavior. NO interfaces.
- **Phase 2**: Given Phase 1 output, derive inputs/outputs with types, sources, consumers.

This tests whether separating interface concerns from structural decomposition reduces
the routing pattern rate by allowing focused attention on tree structure rules in Phase 1.

---

## Results

| # | Trial | Phase1 Children | Phase2 Children | Phase1 Routing | Phase2 Routing | Change |
|---|-------|----------------|----------------|---------------|---------------|--------|
| 0 | trial_02 | 9 | 9 | ROUTING | ROUTING | same |
| 1 | trial_00 | 9 | 9 | ROUTING | ROUTING | same |
| 2 | trial_01 | 9 | 9 | ROUTING | ROUTING | same |
| 3 | trial_04 | 10 | 10 | ROUTING | ROUTING | same |
| 4 | trial_03 | 9 | 9 | ROUTING | ROUTING | same |

## Summary

Phase 1 routing rate: 5/5 (100%)
Phase 2 routing rate: 5/5 (100%)

### Comparison with Baseline

Baseline (single-pass, from routing ablation experiment): 5/5 = 100% routing for order_real. 10 nodes per decomposition.

---

## Phase 1 Decompositions Detail

### Trial 02
- Phase 1 children: CommandRouter, CreateOrderHandler, PayOrderHandler, ShipOrderHandler, CompleteOrderHandler, CancelOrderHandler, ListOrdersHandler, GetUserOrdersHandler, ListProductsHandler
- Routing: True
- Sibling calls: [{"from": "CommandRouter", "to": "CreateOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "PayOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ShipOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "CompleteOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "CancelOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListOrdersHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "GetUserOrdersHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListProductsHandler", "method": "structural_router"}]
- Phase 2 children: CommandRouter, CreateOrderHandler, PayOrderHandler, ShipOrderHandler, CompleteOrderHandler, CancelOrderHandler, ListOrdersHandler, GetUserOrdersHandler, ListProductsHandler
- Routing: True
- Sibling calls: [{"from": "CommandRouter", "to": "CreateOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "PayOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ShipOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "CompleteOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "CancelOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListOrdersHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "GetUserOrdersHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListProductsHandler", "method": "structural_router"}]

### Trial 00
- Phase 1 children: CommandRouter, CreateOrder, PayOrder, ShipOrder, CompleteOrder, CancelOrder, ListOrders, GetUserOrders, ListProducts
- Routing: True
- Sibling calls: [{"from": "CommandRouter", "to": "CreateOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "PayOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "ShipOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "CompleteOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "CancelOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListOrders", "method": "structural_router"}, {"from": "CommandRouter", "to": "GetUserOrders", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListProducts", "method": "structural_router"}]
- Phase 2 children: CommandRouter, CreateOrder, PayOrder, ShipOrder, CompleteOrder, CancelOrder, ListOrders, GetUserOrders, ListProducts
- Routing: True
- Sibling calls: [{"from": "CommandRouter", "to": "CreateOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "PayOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "ShipOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "CompleteOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "CancelOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListOrders", "method": "structural_router"}, {"from": "CommandRouter", "to": "GetUserOrders", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListProducts", "method": "structural_router"}]

### Trial 01
- Phase 1 children: CommandRouter, CreateOrder, PayOrder, ShipOrder, CompleteOrder, CancelOrder, ListOrders, GetUserOrders, ListProducts
- Routing: True
- Sibling calls: [{"from": "CommandRouter", "to": "CreateOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "PayOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "ShipOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "CompleteOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "CancelOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListOrders", "method": "structural_router"}, {"from": "CommandRouter", "to": "GetUserOrders", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListProducts", "method": "structural_router"}]
- Phase 2 children: CommandRouter, CreateOrder, PayOrder, ShipOrder, CompleteOrder, CancelOrder, ListOrders, GetUserOrders, ListProducts
- Routing: True
- Sibling calls: [{"from": "CommandRouter", "to": "CreateOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "PayOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "ShipOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "CompleteOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "CancelOrder", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListOrders", "method": "structural_router"}, {"from": "CommandRouter", "to": "GetUserOrders", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListProducts", "method": "structural_router"}]

### Trial 04
- Phase 1 children: CommandRouter, CreateOrderHandler, PayOrderHandler, ShipOrderHandler, CompleteOrderHandler, CancelOrderHandler, ListOrdersHandler, GetUserOrdersHandler, ListProductsHandler, ResponseFormatter
- Routing: True
- Sibling calls: [{"from": "CommandRouter", "to": "CreateOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "PayOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ShipOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "CompleteOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "CancelOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListOrdersHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "GetUserOrdersHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListProductsHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ResponseFormatter", "method": "structural_router"}]
- Phase 2 children: CommandRouter, CreateOrderHandler, PayOrderHandler, ShipOrderHandler, CompleteOrderHandler, CancelOrderHandler, ListOrdersHandler, GetUserOrdersHandler, ListProductsHandler, ResponseFormatter
- Routing: True
- Sibling calls: [{"from": "CommandRouter", "to": "CreateOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "PayOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ShipOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "CompleteOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "CancelOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListOrdersHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "GetUserOrdersHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListProductsHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ResponseFormatter", "method": "structural_router"}]

### Trial 03
- Phase 1 children: CommandRouter, CreateOrderHandler, PayOrderHandler, ShipOrderHandler, CompleteOrderHandler, CancelOrderHandler, ListOrdersHandler, GetUserOrdersHandler, ListProductsHandler
- Routing: True
- Sibling calls: [{"from": "CommandRouter", "to": "CreateOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "PayOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ShipOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "CompleteOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "CancelOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListOrdersHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "GetUserOrdersHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListProductsHandler", "method": "structural_router"}]
- Phase 2 children: CommandRouter, CreateOrderHandler, PayOrderHandler, ShipOrderHandler, CompleteOrderHandler, CancelOrderHandler, ListOrdersHandler, GetUserOrdersHandler, ListProductsHandler
- Routing: True
- Sibling calls: [{"from": "CommandRouter", "to": "CreateOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "PayOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ShipOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "CompleteOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "CancelOrderHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListOrdersHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "GetUserOrdersHandler", "method": "structural_router"}, {"from": "CommandRouter", "to": "ListProductsHandler", "method": "structural_router"}]
