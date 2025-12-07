"""Simulated user agent for testing customer support agents."""

from dataclasses import dataclass
from enum import Enum

from strands import Agent


class UserPersona(Enum):
    """Different user personas for simulation."""

    POLITE = "polite"  # 丁寧な顧客
    FRUSTRATED = "frustrated"  # 困っている顧客
    CONFUSED = "confused"  # 混乱している顧客
    DETAILED = "detailed"  # 詳細を求める顧客


@dataclass
class UserScenario:
    """Scenario for user simulation.

    Attributes:
        persona: The user persona type.
        initial_query: The initial question/problem.
        goal: What the user wants to achieve.
        context: Additional context about the situation.
        max_turns: Maximum conversation turns.
    """

    persona: UserPersona
    initial_query: str
    goal: str
    context: str = ""
    max_turns: int = 3


# System prompts for different personas
PERSONA_PROMPTS: dict[UserPersona, str] = {
    UserPersona.POLITE: """あなたは丁寧で礼儀正しい顧客を演じてください。

## 振る舞い
- 敬語を使用する
- 感謝の言葉を添える
- 質問は明確に伝える
- サポート担当者の回答を尊重する

## 会話スタイル
「お忙しいところ恐れ入ります」「ありがとうございます」などの
丁寧な表現を使用してください。
""",
    UserPersona.FRUSTRATED: """あなたは困っていて少しイライラしている顧客を演じてください。

## 振る舞い
- 問題に対する不満を表現する（ただし暴言は避ける）
- 早く解決したいという焦りを見せる
- 詳しい説明よりも結論を求める

## 会話スタイル
「困っているんですが」「早く解決したい」などの
緊急性を感じさせる表現を使用してください。
ただし、失礼にならない範囲で表現してください。
""",
    UserPersona.CONFUSED: """あなたは状況がよく分からず混乱している顧客を演じてください。

## 振る舞い
- 質問が曖昧になりがち
- 同じことを別の言い方で確認する
- 手順の確認を求める

## 会話スタイル
「よく分からないのですが」「つまり〇〇ということですか？」などの
確認や再説明を求める表現を使用してください。
""",
    UserPersona.DETAILED: """あなたは詳細な情報を求める顧客を演じてください。

## 振る舞い
- 具体的な条件や例外を確認する
- 追加の質問をする
- 書面やURLなどのエビデンスを求める

## 会話スタイル
「具体的には」「例外はありますか」「どこに記載されていますか」などの
詳細を確認する表現を使用してください。
""",
}


def _build_scenario_prompt(scenario: UserScenario) -> str:
    """Build the complete system prompt for a scenario.

    Args:
        scenario: The user scenario.

    Returns:
        Complete system prompt combining persona and scenario.
    """
    persona_prompt = PERSONA_PROMPTS[scenario.persona]

    scenario_section = f"""
## あなたのシナリオ
- 目的: {scenario.goal}
- 状況: {scenario.context if scenario.context else "特になし"}

## 重要な制約
- 最大{scenario.max_turns}回のやり取りで目的を達成してください
- 目的が達成されたら「ありがとうございました」と締めくくってください
- カスタマーサポートの回答に対して自然に反応してください
- あなたは顧客役なので、自分で問題を解決しようとしないでください

## 最初の発言
会話の最初のターンでは、以下の質問から始めてください：
「{scenario.initial_query}」
"""
    return persona_prompt + scenario_section


def create_simulated_user_agent(
    scenario: UserScenario,
    callback_handler: object | None = None,
) -> Agent:
    """Create a simulated user agent for testing.

    Args:
        scenario: The user scenario to simulate.
        callback_handler: Optional callback handler for streaming output.
            Pass None to disable console output.

    Returns:
        Configured simulated user agent.
    """
    system_prompt = _build_scenario_prompt(scenario)

    agent = Agent(
        system_prompt=system_prompt,
        tools=[],  # Simulated user doesn't need tools
        callback_handler=callback_handler,
    )

    return agent


def get_simulated_user_response(agent: Agent, support_response: str) -> str:
    """Get a response from the simulated user agent.

    Args:
        agent: The simulated user agent instance.
        support_response: The customer support agent's response.

    Returns:
        The simulated user's response as a string.
    """
    prompt = f"""カスタマーサポートからの回答:
{support_response}

上記の回答を受けて、あなたの役割に沿った自然な返答をしてください。
目的が達成されたと感じたら、感謝を述べて会話を終えてください。
"""
    result = agent(prompt)
    return str(result)


# Pre-defined test scenarios
SAMPLE_SCENARIOS: list[UserScenario] = [
    UserScenario(
        persona=UserPersona.POLITE,
        initial_query="商品を返品したいのですが、手続きを教えていただけますか？",
        goal="返品手続きの方法を理解する",
        context="購入から2週間経過、商品は未開封",
        max_turns=3,
    ),
    UserScenario(
        persona=UserPersona.FRUSTRATED,
        initial_query="注文した商品がまだ届かないんですが、どうなっているんですか？",
        goal="配送状況を確認し、いつ届くか知る",
        context="注文から1週間経過",
        max_turns=3,
    ),
    UserScenario(
        persona=UserPersona.CONFUSED,
        initial_query="パスワードがわからなくなってしまって...",
        goal="パスワードをリセットしてログインできるようにする",
        context="メールアドレスは覚えている",
        max_turns=4,
    ),
    UserScenario(
        persona=UserPersona.DETAILED,
        initial_query="返品ポリシーについて詳しく教えてください",
        goal="返品の条件、期限、送料負担について全て確認する",
        context="高額商品を購入検討中",
        max_turns=4,
    ),
]
