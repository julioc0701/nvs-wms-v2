# 04 — Gerenciar IPs de um aplicativo

Fonte: `/pt_br/gerenciar-ips-de-um-aplicativo` (atualizada 30/12/2025). Destilado.

## O que é
- Tela no DevCenter pra configurar **intervalos de IP permitidos** (lista branca) que podem consumir as APIs do app.
- **EXCLUSIVO pra integradores white-listed** (na prática: parceiros / DPP). Se a opção não aparece, o app não está habilitado.
- Formato **CIDR** (IPv4/IPv6). Adição individual ou em massa (CSV sem cabeçalho, IPs separados por vírgula). Há um **limite** de intervalos disponíveis. Dá pra apagar intervalos.

## Implicações pro nosso debate (IP vs cota)
- ML **suporta** restrição por IP — mas como **lista branca opt-in**, e **só pra parceiro**. Não é punição automática de IP de datacenter.
- Se um IP fora da lista chamar → seria **403** (acesso negado), não 429. Coerente com a doc de OAuth ([[03-autenticacao-autorizacao]]): IP = 403, rate-limit = 429.
- **Não explica nosso 429.** Mas dá uma alavanca futura: virando **parceiro (DPP)**, poderíamos **whitelistar o IP de egress do Railway** — útil pra estabilidade/segurança, não pra cota.
- Reforça: nosso 429 é **cota/rate**, não bloqueio de IP.
