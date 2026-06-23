# MultiCamStudio

Parent repository for the MultiCamStudio deployment split.

## Repositories

- `pc/` - `carmenio/MultiCamStudio-PC`, authoritative backend, processing, Supabase schema, task worker, model manager, and media serving.
- `laptop/` - `carmenio/MultiCamStudio-Laptop`, laptop edge stack, operator UI, phone camera app, signaling, edge relay, and proxy.

## Clone

```powershell
git clone --recurse-submodules https://github.com/carmenio/MultiCamStudio.git
cd MultiCamStudio
```

If the parent was cloned without submodules:

```powershell
git submodule update --init --recursive
```

## Commands

```powershell
npm run pc
npm run laptop
npm run pc:logs
npm run laptop:logs
```

Each child repo has its own `.env.example`; copy it to `.env` inside that child before starting its stack.
