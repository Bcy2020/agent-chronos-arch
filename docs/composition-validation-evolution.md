# 父子组合验证：演进路线

## 1. 问题

当前验证体系（MVP-0.4.x）覆盖了语法级和接口级检查，但缺少对 **父子组合行为** 的验证：

- AST Validator 能检查子节点签名是否被调用，但无法知道调用链是否能跑通
- CodeGenerator 能主动拒绝不可实现的分解，但无法验证已生成的代码是否真的能组合运行

父子组合验证的目的是：每一层父节点通过子节点接口实现的代码，在组合层面是否成立。

## 2. BFS 两阶段架构

组合验证引入了一个 DFS 无法满足的约束：**验证父节点时，子节点必须已就绪**（无论是作为 stub、mock 还是 real code）。

因此 TreeBuilder 必须从 DFS 重构为两阶段架构：

```
Phase 1 — 展开（BFS，逐层分解）：
  [root]
    ├── decompose(root) → [a, b, c]
    ├── decompose(a), decompose(b), decompose(c) → [a1, a2, b1, c1, c2]   ← 并行
    ├── ...
    └── 直到所有叶节点停止分解
        输出：完整的节点树（代码为空，接口完整）

Phase 2 — 闭合（自底向上，逐层代码生成 + 组合验证）：
  level N:     codegen(leaf1), codegen(leaf2), ...                           ← 并行
  level N-1:   codegen(parents) → compose(parents with stubs/mocks/real)
  ...
  level 0:     codegen(root) → compose(root)
        输出：完整的节点树（代码就绪，每层已验证）
```

### 2.1 为什么 DFS 不够

当前流程：`decompose(parent) → codegen(parent) → AST(parent) → process(child) → ...`

这在仅依赖接口时可行，但组合验证需要：
- **Stub 模式**：父节点需要子节点的类型信息（这来自接口，DFS 也够）
- **Mock 模式**：TestGenerator 需要所有子节点的职责边界做全局映射——父子同级分解时需要全局视野
- **Real 模式**：父节点需要子节点真实代码，即子节点必须先于父节点生成——DFS 做不到，必须是自底向上

### 2.2 Phase 1：BFS 展开

```
def expand_tree(root, decomposer, config):
    queue = [root]
    visualizer = TreeVisualizer()
    
    while queue:
        level_size = len(queue)
        
        # 并行分解当前层的所有节点
        with ThreadPoolExecutor(max_workers=config.max_workers) as pool:
            futures = []
            for node in queue[:level_size]:
                if not node.stop_decompose and node.depth < config.max_depth:
                    future = pool.submit(decomposer.decompose, node)
                    futures.append((future, node))
            
            for future, node in futures:
                decomposition = future.result()
                node.children = decomposition.children
                node.children_contracts = decomposition.contracts
        
        visualizer.update(tree=root)
        
        # 将下一层的节点加入队列
        next_level = []
        for node in queue[:level_size]:
            next_level.extend(node.children)
        queue = next_level
    
    visualizer.finalize(tree=root)
    return root
```

**并行可行性分析**：
- Phase 1 中每个节点的分解独立于同层其他节点
- 每层内部没有数据依赖（同层节点只需感知父节点的上下文字段，这是只读的）
- 唯一需要关注的是 LLM API 调用频率限制（通过 `max_workers` 控制）
- InterfacePlan 在根节点建立，子节点只从父节点接口继承，不产生跨节点冲突

### 2.3 Phase 2：自底向上闭合

```
def close_tree(root, codegen, validator, composition_validator, provider_cls):
    # 逆序遍历：从最深叶节点到根
    nodes_by_depth = collect_nodes_by_depth_desc(root)
    
    for depth, nodes in nodes_by_depth:
        with ThreadPoolExecutor(max_workers=config.max_workers) as pool:
            futures = []
            for node in nodes:
                if node.stop_decompose:
                    future = pool.submit(process_leaf, node, codegen, validator)
                else:
                    future = pool.submit(process_parent, node, codegen, 
                                        validator, composition_validator, provider_cls)
                futures.append((future, node))
            
            for future, node in futures:
                result = future.result()
                node.code = result.code
                node.validation = result.validation
```

Phase 2 中同层节点的代码生成也互相独立，可并行。

## 3. 交互式树可视化

BFS 展开后，同一时间活跃的节点数量远多于 DFS，控制台 print 不足以管理状态。需要一个可视化模块。

### 3.1 TreeVisualizer 模块

```python
class TreeVisualizer:
    """
    维护树结构状态，输出交互式 HTML 可视化。
    - 每次状态变更后刷新 HTML
    - 支持热加载（HTML 自刷新）
    - 无外部依赖（纯内联 CSS/JS）
    """
    
    def __init__(self, output_path: str):
        self.output_path = output_path
        self.history = []  # 状态快照时间线
    
    def update(self, tree: Node):
        """记录当前树状态，重写 HTML 文件。"""
        snapshot = self._capture(tree)
        self.history.append(snapshot)
        self._render_html(snapshot)
    
    def _capture(self, tree: Node) -> dict:
        """递归捕获节点的结构化状态。"""
        ...
    
    def _render_html(self, snapshot: dict):
        """生成自包含 HTML，含交互式树 + 时间线。"""
        ...
```

### 3.2 节点状态与颜色映射

| 状态 | 颜色 | 含义 |
|------|------|------|
| `pending` | 灰色 | 未开始处理 |
| `decomposing` | 蓝色 | 正在分解 |
| `decomposed` | 青色 | 分解完成，等待代码生成 |
| `codegen` | 橙色 | 正在生成代码 |
| `codegen_failed` | 红色 | 代码生成失败 |
| `validated` | 绿色 | 验证通过 |
| `composition_failed` | 红色 | 组合验证失败 |
| `human_intervention` | 深红 | 需要人工介入 |

### 3.3 HTML 输出特性

- 树状展开/折叠
- 节点点击显示详情面板（purpose、inputs/outputs、errors、code 预览）
- 状态色彩编码（可筛选：只看失败节点）
- 自动刷新（`setInterval` 重新加载 JSON 数据）
- 时间线播放（展开过程的动态回放）

### 3.4 日志输出重构

当前 `TreeBuilder._log()` 分散在多个方法里，BFS 后不再适用。改为 TreeVisualizer 驱动：

```python
# 不再有零散 print
# 所有状态信息通过 TreeVisualizer 统一管理
visualizer = TreeVisualizer(output_path)
visualizer.update(root)

# 控制台只输出进度摘要
visualizer.print_summary()
# 输出示例:
# [Phase 1] Depth 3: 12/15 nodes decomposed, 3 pending | tree.html
# [Phase 2] Level 4: 8/12 nodes codegen'd, 0 failed
```

## 4. 组合验证的统一架构

Phase 2 中所有的组合验证共享同一套执行骨架，只在"子节点实现来源"这一步分化。

```
                     ┌─────────────────────────────────────┐
                     │       Composition Harness            │
                     │  import parent → inject impls → run  │
                     └──────────┬──────────────────────────┘
                                │ delegate (接口)
                                ▼
                     ┌─────────────────────────────────────┐
                     │      ChildImplProvider (ABC)         │
                     ├──────────────────┬───────────────────┐
                     │  StubProvider    │  MockProvider     │
                     │  (0.5.0)         │  (0.5.1)          │
                     └──────────────────┴───────────────────┘
                                            ┆
                                     ┌─────┴──────┐
                                     │ TestGenerator │
                                     │ LLM (0.5.1)   │
                                     └────────────┘
```

### 4.1 Composition Harness

```python
class CompositionValidationResult:
    passed: bool
    per_test: List[TestResult]
    errors: List[str]
    provider_mode: str  # stub / mock / real

class TestResult:
    test_id: str
    crashed: bool
    crash_info: Optional[str]
    return_value: Optional[Any]
    expected_value: Optional[Any]
    value_match: Optional[bool]

class CompositionHarness:
    def __init__(self, provider: ChildImplProvider):
        self.provider = provider
    
    def validate(self, parent: Node, tests: List[TestCase]) -> CompositionValidationResult:
        """1. import parent code  2. inject child impls  3. run tests  4. report"""
```

### 4.2 ChildImplProvider 接口

```python
class ChildImplProvider(ABC):
    @abstractmethod
    def get_impl(self, child_name: str, contract: ChildContract) -> Callable:
        """返回子节点的替身实现。"""
```

三种模式共享此接口，Harness 不需要感知具体实现类的差异。

### 4.3 Node 模型扩展

```python
@dataclass
class TestCase:
    test_id: str
    description: str
    input: Dict[str, Any]          # 父函数参数
    expected_output: Any           # 预期返回值

@dataclass
class ChildMockSpec:
    """TestGenerator 的输出：子节点在某个父测试中的行为。"""
    expected_input: Dict[str, Any]
    return_value: Any

# Node 新增字段:
#   parent_tests: List[TestCase] = field(default_factory=list)
#   child_mock_specs: List[Dict[str, List[ChildMockSpec]]] = field(default_factory=list)
#     索引对齐 parent_tests
```

## 5. 演进路线

### 5.1 MVP-0.5.0：BFS 两阶段架构 + Stub 组合验证

**目标**：完成 TreeBuilder 从 DFS 到 BFS 两阶段的重构，引入交互式可视化，在 Phase 2 中实现 Stub 模式的组合验证。

**提交序列**：

```
commit 1: TreeBuilder 重构为 Phase 1 (BFS expansion) + Phase 2 (bottom-up closure)
          - BFS 逐层分解，自底向上代码生成
          - 支持 ThreadPoolExecutor 并行分解
          - 保持现有 Model/Decomposer/CodeGenerator/Validator 接口不变

commit 2: TreeVisualizer 模块
          - 交互式 HTML 树可视化（内联 CSS/JS，无外部依赖）
          - 节点状态管理：pending → decomposing → decomposed → codegen → validated
          - 自动刷新，时间线回放
          - 替代零散 print 日志

commit 3: CompositionHarness + StubProvider
          - ChildImplProvider 抽象接口
          - StubProvider：从 ChildContract 推导类型默认值 (int→0, str→"", list→[], ...)
          - CompositionHarness：注入 stubs → 运行父节点 → 捕获崩溃
          - 验证失败 → 错误进入 redecomposition 回路

commit 4: Phase 2 集成组合验证
          - 自底向上执行时，每层先 codegen → AST validate → composition validate(stub)
          - TreeVisualizer 同步展示验证状态
          - 并行代码生成（同层节点独立）
```

**StubProvider 行为**：

```
子节点签名                    → 存根返回值
def list_items() -> List[str]  → []
def get_user(id: int) -> dict  → {}
def calc_score() -> int        → 0
def validate() -> bool         → False
def process(x: Any) -> Any     → None
```

**验证通过条件**：Stub 模式不要求返回值正确，只要代码能完整执行（import 不报错、调用链不崩溃、无未捕获异常）。

**成功标准**：
- 展开阶段：BFS 逐层分解，同层节点并行，输出完整树结构
- 闭合阶段：自底向上代码生成 + Stub 组合验证
- 可视化：树结构可看、状态可追踪、失败可定位

### 5.2 MVP-0.5.1：Mock 组合验证

**目标**：在 Phase 2 中引入 TestGenerator LLM，实现 Mock 模式下的语义级组合验证。

**提交序列**：

```
commit 1: TestGenerator LLM
          - 根据父节点 tests + 子节点 contracts + 分解上下文
          - 推导 child_mock_specs（每个父测试用例 → 每个子节点的 IO 对）
          - 输出写入 Node 模型

commit 2: MockProvider
          - 读取 child_mock_specs，根据调用参数返回预设值
          - 支持调用顺序匹配和多次调用匹配

commit 3: TreeBuilder 模式开关
          - --composition-mode stub|mock
          - Mock 模式自动运行 TestGenerator → MockProvider → 验证
          - 预埋 RealProvider 骨架
```

**TestGenerator 推理示例**：

```
父测试: input={user_id: 1} → expected_output={name: "Alice", items: [...]}
子节点 A (fetch_user): 负责根据 user_id 查用户信息
子节点 B (list_items): 负责根据用户 ID 列出物品

推导:
  Child A 应被调用: {user_id: 1} → 返回 {name: "Alice", ...}
  Child B 应被调用: {user_id: 1} → 返回 [...]
```

### 5.3 MVP-1.0：代码管道 + Real 组合验证

**目标**：代码可执行，Phase 2 中激活 RealProvider，实现三级验证贯穿。

```
commit 1: 代码执行管道
          - 生成代码的文件系统组织（节点输出目录结构规范化）
          - 依赖管理（import 路径、跨节点引用）
          - 执行环境（测试运行器）

commit 2: RealProvider
          - 通过 importlib 加载已保存的子节点真实代码
          - 级联执行：叶节点真实实现 → 父节点通过真实子节点运行

commit 3: 三级验证协作
          Phase 2 中每层:
            1. CodeGen
            2. AST Validate
            3. Stub Composition Validate  ← 快速烟雾，每次都跑
            4. TestGenerator + Mock Validate  ← 语义验证，关键路径
            5. Real Composition Validate  ← 真实子节点执行
```

### 5.4 版本一览

| 版本 | 主题 | 解决的问题 |
|------|------|-----------|
| **0.5.0** | BFS 两阶段架构 + 可视化 + Stub 验证 | DFS 无法支持组合验证；控制台日志不足以管理 BFS 的活跃节点；生成代码的可运行性未被验证 |
| **0.5.1** | Mock 组合验证 | 在无真实代码时验证父节点组合逻辑的语义正确性 |
| **1.0** | 代码管道 + Real 验证 | 代码可执行；全真组合验证闭环；三级验证贯穿树构建 |

## 6. 预埋策略

| 预埋项 | 所在版本 | 真正使用 | 预埋方式 |
|--------|---------|---------|---------|
| `Node.parent_tests` | 0.5.0 | 0.5.0 | 字段存在（可空列表） |
| `ChildImplProvider` 接口 | 0.5.0 | 0.5.0 | 直接在 CompositionHarness 中定义为 ABC |
| `CompositionHarness` | 0.5.0 | 0.5.0 | 实现 stub 模式，预留 provider 插槽 |
| `Node.child_mock_specs` | 0.5.0 | 0.5.1 | 数据定义存在，内容为空 |
| `MockProvider` 类 | 0.5.0 | 0.5.1 | 骨架代码 + NotImplementedError |
| `TestGenerator` schema | 0.5.0 | 0.5.1 | prompt 结构和输出格式定义在注释中 |
| `RealProvider` 类 | 0.5.1 | 1.0 | 骨架代码 + NotImplementedError |

## 7. 与现有系统的关系

当前系统状态（MVP-0.4.4）：

```
        ┌──────────────────────────────┐
        │  TreeBuilder (DFS)           │
        │  decompose → codegen → AST   │
        │  → child → ... → sibling     │
        └──────────────────────────────┘
```

0.5.0 后的架构：

```
        ┌──────────────────────────────────────────┐
        │  TreeBuilder (BFS 两阶段)                  │
        │                                            │
        │  Phase 1 — 展开:                           │
        │    level 0 decompose │ level 1 decompose   │
        │    │← parallel →│    │← parallel →│        │
        │    TreeVisualizer ← 实时状态记录            │
        │                                            │
        │  Phase 2 — 闭合:                           │
        │    level N codegen │ level N-1 compose     │
        │    │← parallel →│    │← parallel →│        │
        │    ├── AST Validate                        │
        │    └── CompositionValidate (stub/mock/real)│
        │         → 失败进入 redecomposition 回路     │
        └──────────────────────────────────────────┘
```

CompositionValidator 的错误格式对齐现有 `ValidationResult.errors` + `retry_count`，重分解回路不需要改造。
