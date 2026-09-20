import React, { useEffect, useState } from "react";
import { BookOpen, Search, Globe, Sparkles, Loader2, FileText, CheckCircle2, ArrowRight } from "lucide-react";
import { KnowledgeHit, nexoraApi } from "../../../api/client";

export function KnowledgePage() {
  const [domainToLearn, setDomainToLearn] = useState("python");
  const [useWeb, setUseWeb] = useState(true);
  const [searchQuery, setSearchQuery] = useState("python");

  const [status, setStatus] = useState<{ domains: number; entries: number } | null>(null);
  const [domains, setDomains] = useState<Array<{ name: string; status: string; summary: string; sources: string[] }>>([]);
  const [hits, setHits] = useState<KnowledgeHit[]>([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const loadKnowledge = () => {
    nexoraApi
      .knowledge()
      .then((res) => {
        setStatus(res.status);
        setDomains(res.domains || []);
      })
      .catch((err) => setMessage(`Knowledge fetch error: ${err.message}`));
  };

  useEffect(() => {
    loadKnowledge();
  }, []);

  const handleLearn = async () => {
    if (!domainToLearn.trim()) return;
    setLoading(true);
    setMessage("");
    try {
      const res = await nexoraApi.knowledgeLearn(domainToLearn.trim(), useWeb);
      setMessage(String(res.message || `Learned ${domainToLearn}`));
      setSearchQuery(domainToLearn);
      loadKnowledge();

      const searchRes = await nexoraApi.knowledgeSearch(domainToLearn.trim(), "", 8);
      setHits(searchRes.items || []);
    } catch (err) {
      setMessage(`Learning failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    setMessage("");
    try {
      const searchRes = await nexoraApi.knowledgeSearch(searchQuery.trim(), "", 8);
      setHits(searchRes.items || []);
      setMessage(`Found ${(searchRes.items || []).length} knowledge entries for "${searchQuery}".`);
    } catch (err) {
      setMessage(`Search failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col p-6 space-y-6 overflow-y-auto no-scrollbar font-mono text-xs select-none">
      {/* 1. Header */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-base font-bold text-slate-100 uppercase tracking-widest flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-cyan-400" />
            Knowledge Base & Web Documentation
          </h1>
          <p className="text-[11px] text-slate-500 font-sans mt-0.5">
            Structured, source-attributed domain knowledge — expanded dynamically without model retraining
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs">
          <div className="px-3 py-1 rounded bg-slate-900 border border-slate-800 text-slate-300">
            <span className="text-cyan-400 font-semibold">{status?.domains ?? 0}</span> Domains /{" "}
            <span className="text-cyan-400 font-semibold">{status?.entries ?? 0}</span> Entries
          </div>
        </div>
      </div>

      {/* 2. Web Learning & Search Section */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Learn Domain Card */}
        <div className="p-4 rounded-xl bg-[#090d19] border border-slate-800 space-y-3">
          <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2 border-b border-slate-800 pb-2">
            <Globe className="w-4 h-4 text-cyan-400" />
            Learn & Index New Domain
          </span>

          <div className="space-y-2">
            <div className="flex gap-2">
              <input
                type="text"
                value={domainToLearn}
                onChange={(e) => setDomainToLearn(e.target.value)}
                placeholder="Domain name (e.g. Python, FastAPI, React)..."
                className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-500/50"
              />
              <button
                onClick={handleLearn}
                disabled={loading || !domainToLearn.trim()}
                className="px-4 py-2 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-medium disabled:opacity-40 transition-colors flex items-center gap-1.5"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                <span>Learn</span>
              </button>
            </div>

            <label className="flex items-center gap-2 text-[11px] text-slate-400 cursor-pointer pt-1">
              <input
                type="checkbox"
                checked={useWeb}
                onChange={(e) => setUseWeb(e.target.checked)}
                className="rounded bg-slate-900 border-slate-700 text-cyan-500 focus:ring-0"
              />
              <span>Fetch real documentation from web URLs (?web=true)</span>
            </label>
          </div>
        </div>

        {/* Search Knowledge Card */}
        <div className="p-4 rounded-xl bg-[#090d19] border border-slate-800 space-y-3">
          <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider flex items-center gap-2 border-b border-slate-800 pb-2">
            <Search className="w-4 h-4 text-cyan-400" />
            Search Knowledge Base
          </span>

          <div className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="Search concepts, packages, syntax..."
              className="flex-1 bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-100 outline-none focus:border-cyan-500/50"
            />
            <button
              onClick={handleSearch}
              disabled={loading || !searchQuery.trim()}
              className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 transition-colors flex items-center gap-1.5"
            >
              <Search className="w-4 h-4" />
              <span>Search</span>
            </button>
          </div>
        </div>
      </div>

      {/* Notification Message */}
      {message && (
        <div className="p-3 rounded-lg bg-cyan-950/40 border border-cyan-500/30 text-cyan-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0 text-cyan-400" />
          <span>{message}</span>
        </div>
      )}

      {/* 3. Knowledge Hits & Domain Explorer */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Domain Cards (Left 1 Col) */}
        <div className="p-4 rounded-xl bg-[#090d19] border border-slate-800 space-y-3">
          <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider block border-b border-slate-800 pb-2">
            Registered Domains ({domains.length})
          </span>

          <div className="space-y-2 max-h-96 overflow-y-auto no-scrollbar">
            {domains.map((d) => (
              <div key={d.name} className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-slate-200 font-bold uppercase tracking-wider text-xs">{d.name}</span>
                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                    {d.status}
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 line-clamp-2">{d.summary}</p>
                <div className="text-[10px] text-slate-500 truncate pt-1 border-t border-slate-800/60">
                  Sources: {d.sources?.join(", ")}
                </div>
              </div>
            ))}
            {domains.length === 0 && <span className="text-slate-500">No knowledge domains registered yet.</span>}
          </div>
        </div>

        {/* Search Results Hits (Right 2 Cols) */}
        <div className="lg:col-span-2 p-4 rounded-xl bg-[#090d19] border border-slate-800 space-y-3">
          <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider block border-b border-slate-800 pb-2">
            Knowledge Entries & Search Results ({hits.length})
          </span>

          <div className="space-y-3 max-h-96 overflow-y-auto no-scrollbar">
            {hits.map((hit) => (
              <div key={hit.id} className="p-3.5 rounded-lg bg-slate-900/90 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileText className="w-4 h-4 text-cyan-400" />
                    <span className="text-slate-200 font-semibold text-xs">{hit.title}</span>
                  </div>
                  <span className="text-[10px] text-slate-500 px-2 py-0.5 rounded bg-slate-800 uppercase">
                    Domain: {hit.domain}
                  </span>
                </div>
                <p className="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">{hit.content}</p>
                <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1 border-t border-slate-800/60">
                  <span>Source: {hit.source}</span>
                  <span>Tags: {hit.tags?.join(", ")}</span>
                </div>
              </div>
            ))}

            {hits.length === 0 && (
              <div className="text-slate-500 text-center py-8">
                No search results. Enter a domain or search query above.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
