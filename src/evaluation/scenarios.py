"""Test scenarios for agent evaluation."""

from dataclasses import dataclass


@dataclass
class EvaluationScenario:
    """A scenario for evaluating the customer support agent.

    Attributes:
        name: Unique identifier for the scenario.
        description: Human-readable description.
        initial_query: The user's initial question.
        expected_topics: Topics that should be covered in the response.
        expected_tool_use: Whether the agent should use the knowledge search tool.
    """

    name: str
    description: str
    initial_query: str
    expected_topics: list[str]
    expected_tool_use: bool = True


# Pre-defined evaluation scenarios
EVALUATION_SCENARIOS: list[EvaluationScenario] = [
    EvaluationScenario(
        name="return_policy",
        description="返品ポリシーに関する質問",
        initial_query="商品を返品したいのですが、どうすればいいですか？",
        expected_topics=["30日以内", "未使用・未開封", "返品送料"],
    ),
    EvaluationScenario(
        name="warranty",
        description="保証期間に関する質問",
        initial_query="製品の保証について教えてください",
        expected_topics=["1年間", "メーカー保証", "製造上の欠陥"],
    ),
    EvaluationScenario(
        name="order_cancel",
        description="注文キャンセルに関する質問",
        initial_query="注文をキャンセルしたいのですが可能ですか？",
        expected_topics=["発送前", "キャンセル可能", "マイページ"],
    ),
    EvaluationScenario(
        name="delivery_time",
        description="配送時間に関する質問",
        initial_query="注文してからどれくらいで届きますか？",
        expected_topics=["2-5営業日", "離島", "速達配送"],
    ),
    EvaluationScenario(
        name="password_reset",
        description="パスワードリセットに関する質問",
        initial_query="パスワードを忘れてしまいました",
        expected_topics=["パスワードをお忘れの方", "リセットリンク", "メールアドレス"],
    ),
    EvaluationScenario(
        name="payment_methods",
        description="支払い方法に関する質問",
        initial_query="どのような支払い方法が使えますか？",
        expected_topics=["クレジットカード", "銀行振込", "コンビニ払い"],
    ),
    EvaluationScenario(
        name="installment",
        description="分割払いに関する質問",
        initial_query="分割払いはできますか？",
        expected_topics=["分割払い", "3回", "6回", "12回"],
    ),
    EvaluationScenario(
        name="receipt",
        description="領収書に関する質問",
        initial_query="領収書を発行してほしいのですが",
        expected_topics=["マイページ", "注文履歴", "PDF"],
    ),
]
