# Codex Open Source Fund başvuru notları

> Bu dosya kişisel notun; GitHub'a yüklemeden önce silebilir veya `.gitignore`'a ekleyebilirsin.

## Yapılacaklar (başvurmadan önce)

1. GitHub'da `emrsc1/pr-sentinel` adıyla public repo aç ve bu klasörü yükle.
2. `v0.1.0` etiketi ve `v0` etiketi oluştur (`uses: emrsc1/pr-sentinel@v0` bunun için).
3. Repo ayarlarında `OPENAI_API_KEY` secret'ını ekle; açacağın test PR'larında botun yorumunu gör.
4. GitHub Marketplace'te Action olarak yayınla.
5. **En önemlisi:** 3–5 başka açık kaynak projeye kurdur (kendi eski projelerin, arkadaşlarının projeleri, Türk açık kaynak toplulukları). Kaç repoda kurulu olduğu, kaç PR incelediği gibi rakamlar başvuruyu çok güçlendirir.
6. Bir örnek PR yorumunun ekran görüntüsünü README'ye ekle.

## Form alanları (İngilizce yazman önerilir)

**Hangi açık kaynak projesini temsil ediyorsunuz?**

```
PR Sentinel (https://github.com/emrsc1/pr-sentinel)
```

**Projenin kısa açıklaması**

```
PR Sentinel is an MIT-licensed GitHub Action that helps open source maintainers triage pull requests. On every PR it posts a single, continuously updated comment with a plain-language summary, a risk label (risk:low/medium/high), file- and line-specific findings, suggested tests, and a flag for PRs that look low-effort or unreviewed, a growing problem as AI-generated PRs flood popular repos.

It combines free deterministic checks (leaked secrets, CI workflow edits, auth/migration/dependency changes, lockfile drift, missing tests) with an OpenAI model review via the Responses API and strict structured output. Heuristics can only raise the risk level, it's fork-safe (pull_request, not pull_request_target), it degrades gracefully to heuristics-only without a key, and it has zero dependencies.

API credits would let us run PR Sentinel for free on community projects that can't pay for API usage, and fund the roadmap: inline line comments, per-repo rules, duplicate PR detection, and release-note drafting.
```

**Bilmemizi istediğiniz başka bir şey var mı?** (rakamları doldur)

```
PR Sentinel is currently used on [N] repositories and has reviewed [N] pull requests. It reviews its own PRs as dogfooding. I'm also adding Turkish-language support for the Turkish open source community. Credits would be used only for the hosted reviews on public OSS repositories, and I'll publish monthly usage numbers in the repo.
```

**GitHub deposu**

```
https://github.com/emrsc1/pr-sentinel
```

## Not

Model varsayılanı `gpt-5.4`. Başvurudan önce OpenAI'nin güncel model listesine bakıp `action.yml` içindeki varsayılanı gerekirse değiştir.
