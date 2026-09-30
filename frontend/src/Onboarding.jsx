import { useEffect, useRef } from "react";

const CHOICES = [
  {
    level: "beginner",
    title: "我是新手",
    text: "還不熟棋子怎麼走也沒關係。先跟最簡單的電腦下，點一下棋子就會顯示能走的格子。",
  },
  {
    level: "player",
    title: "我會下棋",
    text: "知道規則、想練實戰。跟中階電腦對局，下完可以復盤，隨時問教練。",
  },
  {
    level: "chesscom",
    title: "我在 Chess.com 下棋",
    text: "匯入你的公開對局，找出自己的失誤，再請教練講解。",
  },
];

export function Onboarding({ onChoose, onClose }) {
  const firstChoice = useRef(null);
  useEffect(() => {
    firstChoice.current?.focus();
  }, []);

  return (
    <div className="onboarding-backdrop">
      <section
        className="onboarding-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="onboarding-title"
        onKeyDown={(event) => { if (event.key === "Escape" && onClose) onClose(); }}
      >
        <div className="panel-kicker">歡迎</div>
        <h2 id="onboarding-title">你目前的程度是？</h2>
        <p className="onboarding-lead">選一個最接近的，我們會調整電腦難度和畫面。之後隨時可以再改。</p>
        <div className="onboarding-choices">
          {CHOICES.map((choice, index) => (
            <button
              key={choice.level}
              ref={index === 0 ? firstChoice : undefined}
              className="onboarding-choice"
              onClick={() => onChoose(choice.level)}
            >
              <strong>{choice.title}</strong>
              <span>{choice.text}</span>
            </button>
          ))}
        </div>
        {onClose && (
          <button className="btn btn-ghost btn-sm onboarding-close" onClick={onClose}>先不用，維持目前設定</button>
        )}
      </section>
    </div>
  );
}

export function BeginnerTips({ onDismiss }) {
  return (
    <section className="beginner-tips" aria-label="新手提示">
      <div className="beginner-tips__head">
        <strong>新手提示</strong>
        <button className="btn btn-ghost btn-sm" onClick={onDismiss}>知道了</button>
      </div>
      <ol>
        <li>點一下你的棋子，棋盤上會出現它可以走的點點。</li>
        <li>下完一步，電腦會自動回應。</li>
        <li>不懂就問下面的教練，例如「我剛才那步好嗎？」或「對手想幹嘛？」。</li>
      </ol>
    </section>
  );
}
