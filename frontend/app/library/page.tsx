"use client";

import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";

import {
  type BrowsePick,
  type DiscoveryTurn,
  type SelectedSource,
  SourceBrowser,
  TalkToData,
} from "@/components/lp-library";
import { Button } from "@/components/ui/Button";
import { PageFrame } from "@/components/workbench/PageFrame";

// Leading Practice Library: the chat by default, with Browse sources opening the search screen. Sources checked in
// either can be added to an engagement's sources; those on the search screen stay apart until added or taken to the chat.
export default function LibraryPage() {
  const [browsing, setBrowsing] = useState(false);
  const [practice, setPractice] = useState("");
  const [turns, setTurns] = useState<DiscoveryTurn[]>([]);
  const [selection, setSelection] = useState<SelectedSource[]>([]);
  const [picks, setPicks] = useState<BrowsePick[]>([]);
  const [chatScope, setChatScope] = useState<DiscoveryTurn["scope"]>("broad");

  // Links such as /library?practice=lp-016 open that practice on the source screen.
  useEffect(() => {
    const linked = new URLSearchParams(window.location.search).get("practice");
    if (linked) {
      setPractice(linked);
      setBrowsing(true);
    }
  }, []);

  const toggleSource = (source: SelectedSource) =>
    setSelection((prev) =>
      prev.some((s) => s.practiceId === source.practiceId)
        ? prev.filter((s) => s.practiceId !== source.practiceId)
        : [...prev, source]
    );

  const backToChat = () => {
    setBrowsing(false);
    setPractice("");
  };

  // Having picked sources to continue with, the next answers come from them; the chat's scope control can widen it.
  const continueWithChat = (sources: SelectedSource[]) => {
    setSelection((prev) => [...prev, ...sources.filter((s) => !prev.some((p) => p.practiceId === s.practiceId))]);
    setPicks(() => []);
    setChatScope("selected");
    backToChat();
  };

  return (
    <PageFrame
      breadcrumb={browsing ? "User workspace / Leading Practice Library / Browse sources" : "User workspace / Leading Practice Library"}
      title={browsing ? "Browse sources" : "Leading Practice Library"}
      subtitle={
        browsing
          ? "Search the approved library, check the sources you want and add them to an engagement."
          : "Discover approved guidance, ask questions and choose the sources to take into your engagement."
      }
      actions={
        browsing ? (
          <Button variant="secondary" className="flex items-center gap-2" onClick={backToChat}>
            <ArrowLeft size={16} aria-hidden />
            Back to chat
          </Button>
        ) : null
      }
    >
      {/* Stays mounted while browsing: a half-typed question and an answer still on its way must survive the visit. */}
      <div hidden={browsing}>
        <TalkToData
          turns={turns}
          setTurns={setTurns}
          selection={selection}
          onToggle={toggleSource}
          onBrowse={() => setBrowsing(true)}
          chosenScope={chatScope}
          setScope={setChatScope}
          browsing={browsing}
        />
      </div>
      {browsing ? (
        <SourceBrowser
          picks={picks}
          setPicks={setPicks}
          initialPractice={practice}
          chatSourceIds={selection.map((s) => s.practiceId)}
          onContinue={continueWithChat}
        />
      ) : null}
    </PageFrame>
  );
}
