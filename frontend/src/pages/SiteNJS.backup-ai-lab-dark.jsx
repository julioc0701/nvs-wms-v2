import { useRef, useState } from 'react'
import {
  ArrowRight,
  Bot,
  BrainCircuit,
  CheckCircle2,
  Database,
  FileSearch,
  GitBranch,
  MessageCircle,
  Network,
  Radar,
  Sparkles,
  Workflow,
  Zap,
} from 'lucide-react'
import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'
import { useGSAP } from '@gsap/react'

gsap.registerPlugin(ScrollTrigger, useGSAP)

const whatsappMessage =
  'Oi, vi o site da NJS e quero agendar um diagnostico para mapear oportunidades de IA, agentes e automacao na minha empresa.'
const WHATSAPP_URL = `https://wa.me/5519991246031?text=${encodeURIComponent(whatsappMessage)}`

const focusRing =
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyan-300 focus-visible:ring-offset-2 focus-visible:ring-offset-[#05070d]'

const nodes = [
  {
    id: 'processos',
    label: 'Processos',
    icon: GitBranch,
    x: 8,
    y: 18,
    z: 72,
    copy: 'Mapeamos tarefas, gargalos e decisoes que hoje dependem de memoria, planilha ou conversa solta.',
  },
  {
    id: 'dados',
    label: 'Dados',
    icon: Database,
    x: 68,
    y: 14,
    z: 118,
    copy: 'Organizamos documentos, planilhas e historico para a IA trabalhar com contexto real da empresa.',
  },
  {
    id: 'chatgpt',
    label: 'ChatGPT',
    icon: Sparkles,
    x: 78,
    y: 52,
    z: 52,
    copy: 'Usamos modelos lideres como ferramentas dentro de um fluxo seguro, nao como promessa vazia.',
  },
  {
    id: 'agentes',
    label: 'Agentes',
    icon: Bot,
    x: 48,
    y: 76,
    z: 145,
    copy: 'Criamos agentes que apoiam atendimento, analise, relatorios e operacoes repetitivas.',
  },
  {
    id: 'automacao',
    label: 'Automacao',
    icon: Zap,
    x: 15,
    y: 64,
    z: 96,
    copy: 'Conectamos ferramentas, APIs, WhatsApp, CRM, ERP e planilhas para reduzir trabalho manual.',
  },
]

const stages = [
  ['Diagnostico', 'Mapeamos onde sua operacao perde tempo.'],
  ['Orquestracao', 'Transformamos gargalos em agentes, automacoes e integracoes.'],
  ['Implementacao', 'Testamos, ajustamos e colocamos a IA para apoiar sua equipe.'],
]

const useCases = [
  ['Agente de documentos', 'Busca respostas em politicas, contratos, manuais e procedimentos internos.'],
  ['Relatorios automaticos', 'Coleta dados, resume indicadores e envia alertas sem planilha manual.'],
  ['Atendimento assistido', 'Classifica demanda, sugere resposta e organiza historico para a equipe.'],
  ['Copiloto comercial', 'Gera propostas, e-mails, follow-ups e resumos de reuniao com contexto.'],
  ['Analise operacional', 'Encontra gargalos, divergencias, atrasos e tarefas que podem virar fluxo.'],
  ['Integracao de sistemas', 'Conecta APIs, bancos, CRMs, WhatsApp, planilhas e automacoes.'],
]

const technologies = ['ChatGPT', 'OpenAI', 'Claude', 'Modelos open source', 'n8n', 'Make', 'APIs', 'Agentes NJS']

function LogoMark() {
  return (
    <div className="flex items-center gap-3">
      <div className="relative grid h-12 w-12 place-items-center rounded-2xl border border-cyan-200/20 bg-white/[0.04] shadow-[0_0_40px_rgba(34,211,238,.16)]">
        <div className="absolute inset-1 rounded-xl bg-[conic-gradient(from_140deg,#67e8f9,#a78bfa,#22c55e,#67e8f9)] opacity-70 blur-[10px]" />
        <svg viewBox="0 0 64 64" className="relative h-10 w-10" fill="none" aria-hidden="true">
          <path d="M14 45V19l18 26V19" stroke="white" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
          <path d="M38 18h10c5 0 8 3 8 7s-3 7-8 7h-4c-5 0-8 3-8 8v5" stroke="#67e8f9" strokeWidth="5" strokeLinecap="round" />
          <circle cx="14" cy="45" r="3" fill="#22c55e" />
          <circle cx="32" cy="45" r="3" fill="#67e8f9" />
          <circle cx="49" cy="18" r="3" fill="#a78bfa" />
        </svg>
      </div>
      <div className="leading-none">
        <div className="text-2xl font-black tracking-tight text-white">NJS</div>
        <div className="mt-1 text-[10px] font-black uppercase tracking-[0.22em] text-cyan-100/75">Novais Julio System</div>
      </div>
    </div>
  )
}

function CTAButton({ children = 'Mapear minha operacao', variant = 'primary' }) {
  const base = 'group inline-flex min-h-12 items-center justify-center gap-2 rounded-xl px-5 py-3 text-sm font-black transition'
  const styles =
    variant === 'primary'
      ? 'bg-cyan-300 text-slate-950 shadow-[0_18px_55px_rgba(103,232,249,.28)] hover:-translate-y-0.5 hover:bg-white'
      : 'border border-white/15 bg-white/[0.04] text-white hover:border-cyan-200/70 hover:bg-white/[0.08]'

  return (
    <a href={WHATSAPP_URL} target="_blank" rel="noopener noreferrer" className={`${base} ${styles} ${focusRing}`}>
      {children}
      <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
    </a>
  )
}

function LabHero() {
  const [active, setActive] = useState(nodes[3])

  return (
    <div className="lab-shell relative min-h-[360px] overflow-hidden rounded-[2rem] border border-white/10 bg-[#070b13] shadow-[0_40px_160px_rgba(8,145,178,.22)] md:min-h-[560px]">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_42%,rgba(103,232,249,.22),transparent_26%),radial-gradient(circle_at_82%_10%,rgba(167,139,250,.18),transparent_26%),radial-gradient(circle_at_10%_82%,rgba(34,197,94,.14),transparent_28%)]" />
      <div className="absolute inset-0 opacity-[.22] [background-image:linear-gradient(rgba(103,232,249,.18)_1px,transparent_1px),linear-gradient(90deg,rgba(103,232,249,.18)_1px,transparent_1px)] [background-size:44px_44px]" />
      <div className="scan-beam absolute inset-y-0 left-0 w-1/3 bg-gradient-to-r from-transparent via-cyan-200/20 to-transparent" />

      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {nodes.map((node) => (
          <path
            key={node.id}
            className={`flow-line ${active.id === node.id ? 'is-hot' : ''}`}
            d={`M50 50 C ${node.x} 50, 50 ${node.y}, ${node.x} ${node.y}`}
          />
        ))}
      </svg>

      <div className="lab-scene absolute inset-0 [perspective:1200px]">
        <div className="lab-plane absolute left-1/2 top-1/2 h-[460px] w-[700px] -translate-x-1/2 -translate-y-1/2 rounded-full border border-cyan-200/10" />
        <div className="njs-core absolute left-1/2 top-1/2 z-20 grid h-28 w-28 -translate-x-1/2 -translate-y-1/2 place-items-center rounded-[2rem] border border-cyan-200/30 bg-cyan-300 text-slate-950 shadow-[0_0_90px_rgba(103,232,249,.48)] md:h-36 md:w-36">
          <div className="absolute -inset-6 rounded-[2.4rem] border border-cyan-200/15" />
          <div className="absolute -inset-12 rounded-[3rem] border border-cyan-200/10" />
          <div className="text-center">
            <div className="text-3xl font-black tracking-[-.08em] md:text-4xl">NJS</div>
            <div className="mt-1 font-mono text-[10px] font-black uppercase tracking-[.22em]">Core</div>
          </div>
        </div>

        {nodes.map((node, index) => {
          const Icon = node.icon
          return (
            <button
              key={node.id}
              type="button"
              onMouseEnter={() => setActive(node)}
              onFocus={() => setActive(node)}
              style={{ left: `${node.x}%`, top: `${node.y}%`, transform: `translateZ(${node.z}px)` }}
              className={`process-node absolute z-30 w-36 -translate-x-1/2 -translate-y-1/2 rounded-2xl border p-4 text-left backdrop-blur-xl transition duration-300 ${active.id === node.id ? 'border-cyan-200 bg-cyan-200/14 shadow-[0_0_50px_rgba(103,232,249,.24)]' : 'border-white/10 bg-white/[0.055] hover:border-white/25'}`}
            >
              <div className="flex items-center gap-2">
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-white/10 text-cyan-100">
                  <Icon className="h-5 w-5" />
                </span>
                <span className="text-sm font-black text-white">{node.label}</span>
              </div>
              <div className="mt-3 h-1 overflow-hidden rounded-full bg-white/10">
                <span className="data-packet block h-full w-1/2 rounded-full bg-cyan-200" style={{ animationDelay: `${index * 0.35}s` }} />
              </div>
            </button>
          )
        })}
      </div>

      <div className="absolute bottom-4 left-4 right-4 z-40 rounded-2xl border border-white/10 bg-slate-950/72 p-4 backdrop-blur-xl md:bottom-5 md:left-auto md:right-5 md:w-[380px]">
        <div className="flex items-center justify-between gap-3">
          <div className="font-mono text-[10px] font-black uppercase tracking-[.22em] text-cyan-200">Modulo ativo</div>
          <div className="h-2 w-2 rounded-full bg-emerald-300 shadow-[0_0_0_7px_rgba(52,211,153,.13)]" />
        </div>
        <h3 className="mt-3 text-xl font-black text-white md:text-2xl">{active.label}</h3>
        <p className="mt-2 line-clamp-2 text-sm leading-6 text-slate-300 md:line-clamp-none">{active.copy}</p>
      </div>
    </div>
  )
}

function AgentConsole() {
  const [active, setActive] = useState(0)
  const prompts = [
    ['Onde automatizar primeiro?', 'Comece pelas tarefas frequentes, repetitivas e com regra clara: relatorios, triagem, classificacao e follow-up.'],
    ['Quais dados preciso organizar?', 'Documentos, planilhas, historico de atendimento, indicadores e regras de negocio que hoje vivem espalhados.'],
    ['IA substitui minha equipe?', 'Nao. A NJS desenha agentes para apoiar a equipe, reduzir trabalho manual e manter decisoes criticas sob controle.'],
  ]

  return (
    <div className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,.08)]">
      <div className="rounded-[1.5rem] border border-cyan-200/15 bg-[#060a12] p-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-cyan-300 text-slate-950">
              <Bot className="h-6 w-6" />
            </div>
            <div>
              <div className="font-black text-white">Agente NJS</div>
              <div className="font-mono text-[10px] uppercase tracking-[.2em] text-cyan-100/70">simulacao de diagnostico</div>
            </div>
          </div>
          <Radar className="h-5 w-5 text-emerald-300" />
        </div>

        <div className="grid gap-2">
          {prompts.map(([question], index) => (
            <button
              key={question}
              type="button"
              onClick={() => setActive(index)}
              className={`rounded-xl border px-4 py-3 text-left text-sm font-bold transition ${active === index ? 'border-cyan-200 bg-cyan-200/12 text-white' : 'border-white/10 bg-white/[0.03] text-slate-300 hover:border-white/25'}`}
            >
              {question}
            </button>
          ))}
        </div>

        <div className="mt-4 rounded-xl border border-emerald-200/15 bg-emerald-200/8 p-4">
          <div className="font-mono text-[10px] font-black uppercase tracking-[.22em] text-emerald-200">resposta</div>
          <p className="mt-2 leading-7 text-slate-200">{prompts[active][1]}</p>
        </div>
      </div>
    </div>
  )
}

export default function SiteNJS() {
  const pageRef = useRef(null)
  const labRef = useRef(null)

  useGSAP(() => {
    const ctx = gsap.context(() => {
      gsap.from('.hero-copy > *', {
        y: 28,
        opacity: 0,
        duration: 0.8,
        ease: 'power3.out',
        stagger: 0.08,
      })

      gsap.from('.process-node', {
        y: 20,
        opacity: 0,
        rotateX: -18,
        duration: 1,
        ease: 'back.out(1.8)',
        stagger: 0.08,
        delay: 0.25,
      })

      gsap.to('.lab-plane', {
        rotateX: 64,
        rotateZ: 360,
        duration: 26,
        repeat: -1,
        ease: 'none',
      })

      gsap.utils.toArray('.story-card').forEach((card, index) => {
        gsap.from(card, {
          opacity: 0,
          y: 40,
          rotateX: -10,
          duration: 0.8,
          ease: 'power3.out',
          scrollTrigger: {
            trigger: card,
            start: 'top 82%',
          },
          delay: index * 0.03,
        })
      })

      const mm = gsap.matchMedia()
      mm.add('(min-width: 900px)', () => {
        gsap.to('.lab-shell', {
          scrollTrigger: {
            trigger: '.hero-section',
            start: 'top top',
            end: 'bottom top',
            scrub: 0.6,
          },
          rotateX: 3,
          rotateY: -5,
          scale: 0.94,
          ease: 'none',
        })
      })

      return () => mm.revert()
    }, pageRef)

    return () => ctx.revert()
  }, { scope: pageRef })

  const handlePointerMove = (event) => {
    if (!labRef.current) return
    const rect = labRef.current.getBoundingClientRect()
    const x = (event.clientX - rect.left) / rect.width - 0.5
    const y = (event.clientY - rect.top) / rect.height - 0.5
    labRef.current.style.setProperty('--mx', `${x * 16}deg`)
    labRef.current.style.setProperty('--my', `${y * -12}deg`)
  }

  return (
    <main ref={pageRef} className="njs-page min-h-screen overflow-hidden bg-[#05070d] text-white">
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');
        .njs-page { font-family: 'Manrope', system-ui, sans-serif; }
        .font-mono { font-family: 'JetBrains Mono', monospace; }
        html { scroll-behavior: smooth; }
        .njs-page:before {
          content: "";
          position: fixed;
          inset: 0;
          pointer-events: none;
          opacity: .34;
          background-image: radial-gradient(circle at 1px 1px, rgba(255,255,255,.20) 1px, transparent 0);
          background-size: 26px 26px;
          mask-image: linear-gradient(180deg, #000, transparent 70%);
        }
        .lab-shell { transform: rotateY(var(--mx, 0deg)) rotateX(var(--my, 0deg)); transform-style: preserve-3d; transition: transform .18s ease-out; }
        .lab-scene { transform-style: preserve-3d; }
        .lab-plane {
          transform-style: preserve-3d;
          background-image:
            linear-gradient(rgba(103,232,249,.17) 1px, transparent 1px),
            linear-gradient(90deg, rgba(103,232,249,.17) 1px, transparent 1px);
          background-size: 44px 44px;
          transform: rotateX(64deg) rotateZ(0deg);
          box-shadow: 0 0 90px rgba(34,211,238,.10) inset;
        }
        .flow-line {
          fill: none;
          stroke: rgba(103,232,249,.28);
          stroke-width: .28;
          stroke-dasharray: 4 4;
          animation: dashFlow 7s linear infinite;
        }
        .flow-line.is-hot { stroke: rgba(103,232,249,.88); stroke-width: .48; filter: drop-shadow(0 0 8px rgba(103,232,249,.5)); }
        .scan-beam { animation: scanMove 5.2s ease-in-out infinite; }
        .data-packet { animation: packetMove 2.4s ease-in-out infinite; }
        .njs-core { animation: coreFloat 5s ease-in-out infinite; }
        @keyframes dashFlow { to { stroke-dashoffset: -80; } }
        @keyframes scanMove {
          0% { transform: translateX(-120%); opacity: 0; }
          20%, 70% { opacity: 1; }
          100% { transform: translateX(320%); opacity: 0; }
        }
        @keyframes packetMove {
          0% { transform: translateX(-120%); opacity: 0; }
          30%, 80% { opacity: 1; }
          100% { transform: translateX(220%); opacity: 0; }
        }
        @keyframes coreFloat {
          0%, 100% { transform: translate(-50%, -50%) translateZ(160px); }
          50% { transform: translate(-50%, calc(-50% - 10px)) translateZ(180px); }
        }
        @media (max-width: 767px) {
          .process-node { width: 7.2rem; padding: .7rem; }
          .process-node:nth-of-type(2) { display: none; }
          .process-node:nth-of-type(4) { display: none; }
          .lab-shell { transform: none !important; }
        }
        @media (prefers-reduced-motion: reduce) {
          *, *:before, *:after { animation: none !important; transition: none !important; scroll-behavior: auto !important; }
        }
      `}</style>

      <section className="hero-section relative min-h-screen overflow-hidden">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_0%,rgba(34,211,238,.24),transparent_32%),radial-gradient(circle_at_80%_12%,rgba(167,139,250,.18),transparent_30%),linear-gradient(180deg,#05070d_0%,#09111e_55%,#05070d_100%)]" />
        <header className="relative z-20 mx-auto flex max-w-7xl items-center justify-between px-5 py-6 md:px-8">
          <LogoMark />
          <nav className="hidden items-center gap-6 text-sm font-bold text-slate-300 lg:flex">
            <a href="#diagnostico" className="hover:text-white">Diagnostico</a>
            <a href="#orquestracao" className="hover:text-white">Orquestracao</a>
            <a href="#agentes" className="hover:text-white">Agentes</a>
          </nav>
          <CTAButton variant="ghost">Falar com a NJS</CTAButton>
        </header>

        <div className="relative z-10 mx-auto grid max-w-7xl gap-8 px-5 pb-16 pt-2 md:px-8 lg:grid-cols-[.92fr_1.08fr] lg:items-center lg:gap-10 lg:pt-6">
          <div className="hero-copy order-2 lg:order-1">
            <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-cyan-200/20 bg-cyan-200/10 px-3 py-2 text-xs font-black uppercase tracking-[0.22em] text-cyan-100">
              <Sparkles className="h-4 w-4" />
              AI Operations Lab
            </div>
            <h1 className="max-w-4xl text-[3.2rem] font-black leading-[.88] tracking-[-.065em] text-white md:text-7xl">
              Transforme processos travados em sistemas inteligentes com IA.
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300 md:text-xl">
              A NJS mapeia gargalos, encontra oportunidades reais e implementa agentes, automacoes e integracoes para sua empresa ganhar tempo, clareza e escala.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <CTAButton>Mapear minha operacao</CTAButton>
              <a href="#diagnostico" className={`inline-flex min-h-12 items-center justify-center rounded-xl border border-white/15 px-5 py-3 text-sm font-black text-white transition hover:border-cyan-200/70 hover:bg-white/[0.06] ${focusRing}`}>
                Ver oportunidades de IA
              </a>
            </div>
            <div className="mt-8 grid max-w-2xl gap-3 sm:grid-cols-3">
              {['Diagnostico real', 'Agentes sob controle', 'Automacao implementada'].map((item) => (
                <div key={item} className="rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-sm font-bold text-slate-200">
                  {item}
                </div>
              ))}
            </div>
          </div>

          <div ref={labRef} onPointerMove={handlePointerMove} className="order-1 lg:order-2">
            <LabHero />
          </div>
        </div>
      </section>

      <section id="diagnostico" className="relative border-y border-white/10 bg-white/[0.03] px-5 py-20 md:px-8">
        <div className="mx-auto grid max-w-7xl gap-8 lg:grid-cols-[.85fr_1.15fr]">
          <div className="story-card">
            <p className="font-mono text-xs font-black uppercase tracking-[.26em] text-cyan-200">Diagnostico</p>
            <h2 className="mt-4 text-4xl font-black leading-[.95] tracking-[-.04em] md:text-6xl">
              Antes de automatizar, encontramos onde a empresa perde tempo.
            </h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {['Planilhas duplicadas', 'Atendimento lento', 'Relatorio manual', 'Dados espalhados', 'Follow-up esquecido', 'Equipe apagando incendio'].map((pain, index) => (
              <div key={pain} className="story-card rounded-2xl border border-white/10 bg-slate-950/70 p-5">
                <div className="mb-4 font-mono text-[10px] font-black uppercase tracking-[.2em] text-amber-200">sinal {String(index + 1).padStart(2, '0')}</div>
                <div className="text-xl font-black text-white">{pain}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="orquestracao" className="mx-auto grid max-w-7xl gap-10 px-5 py-24 md:px-8 lg:grid-cols-[1fr_.95fr] lg:items-center">
        <div className="story-card">
          <p className="font-mono text-xs font-black uppercase tracking-[.26em] text-emerald-200">Orquestracao</p>
          <h2 className="mt-4 text-4xl font-black leading-[.95] tracking-[-.04em] md:text-6xl">
            A NJS transforma gargalos em fluxos de agentes, automacoes e integracoes.
          </h2>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
            ChatGPT, OpenAI, Claude e modelos open source entram como ferramentas. A estrategia e o desenho do fluxo ficam com a NJS.
          </p>
          <div className="mt-7 grid grid-cols-2 gap-3 md:grid-cols-4">
            {technologies.map((tech) => (
              <div key={tech} className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-4 text-center text-sm font-black text-slate-100">
                {tech}
              </div>
            ))}
          </div>
        </div>
        <AgentConsole />
      </section>

      <section id="agentes" className="relative bg-slate-900/60 px-5 py-24 md:px-8">
        <div className="mx-auto max-w-7xl">
          <div className="story-card max-w-3xl">
            <p className="font-mono text-xs font-black uppercase tracking-[.26em] text-violet-200">Implementacao</p>
            <h2 className="mt-4 text-4xl font-black leading-[.95] tracking-[-.04em] md:text-6xl">
              IA para reduzir trabalho manual, nao para criar teatro tecnologico.
            </h2>
          </div>

          <div className="mt-10 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {useCases.map(([title, copy]) => (
              <article key={title} className="story-card rounded-2xl border border-white/10 bg-white/[0.04] p-6 transition hover:-translate-y-1 hover:border-cyan-200/40 hover:bg-cyan-200/[0.06]">
                <CheckCircle2 className="h-6 w-6 text-emerald-300" />
                <h3 className="mt-5 text-xl font-black text-white">{title}</h3>
                <p className="mt-3 leading-7 text-slate-300">{copy}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-20 md:px-8">
        <div className="story-card overflow-hidden rounded-[2rem] border border-cyan-200/20 bg-cyan-300 p-8 text-slate-950 shadow-[0_30px_120px_rgba(103,232,249,.18)] md:p-12">
          <div className="grid gap-8 lg:grid-cols-[1fr_auto] lg:items-center">
            <div>
              <h2 className="text-4xl font-black leading-[.95] tracking-[-.04em] md:text-6xl">
                Sua empresa ja tem dados, tarefas e gargalos. Vamos transformar isso em automacao.
              </h2>
              <p className="mt-5 max-w-3xl text-lg font-semibold leading-8 text-slate-800">
                Comece com um diagnostico de IA: processos, oportunidades, riscos e um plano pratico de implementacao.
              </p>
            </div>
            <a href={WHATSAPP_URL} target="_blank" rel="noopener noreferrer" className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-slate-950 px-5 py-3 text-sm font-black text-white transition hover:-translate-y-0.5 hover:bg-slate-800">
              <MessageCircle className="h-4 w-4" />
              Agendar diagnostico
            </a>
          </div>
        </div>
      </section>

      <footer className="border-t border-white/10 px-5 py-8 text-center text-xs leading-6 text-slate-500 md:px-8">
        <p>NJS - Novais Julio System. Consultoria em IA, agentes e automacao.</p>
        <p className="mt-2">
          Marcas e nomes citados pertencem aos seus respectivos proprietarios. O uso indica experiencia tecnica ou compatibilidade, nao parceria oficial.
        </p>
      </footer>
    </main>
  )
}
