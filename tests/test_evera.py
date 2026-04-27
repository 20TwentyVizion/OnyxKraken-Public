"""Quick EVERA connectivity, auto-start, and generation test.

Usage:
    python test_evera.py                # health check only
    python test_evera.py --start        # auto-start EVERA services
    python test_evera.py --generate     # auto-start + generate a 30s test track
    python test_evera.py --shutdown     # shut down EVERA services Onyx started
"""

import sys
import os
import time

def main():
    do_start = "--start" in sys.argv
    do_generate = "--generate" in sys.argv
    do_shutdown = "--shutdown" in sys.argv

    print("=" * 60)
    print("  EVERA Music Engine — Test Suite")
    print("=" * 60)

    from apps.evera_client import EveraClient, EveraClientError
    from apps.evera_service import (
        ensure_evera, is_evera_ready, shutdown_evera, get_service_manager,
    )

    client = EveraClient()
    mgr = get_service_manager()

    # ------------------------------------------------------------------
    # 1. Health check
    # ------------------------------------------------------------------
    print("\n[1] Service Health Check")

    evera_ok = client.is_healthy()
    ace_ok = client.acestep_healthy()
    ollama_ok = mgr.is_ollama_running()

    print(f"    EVERA API  (port 8080): {'✅ OK' if evera_ok else '❌ OFFLINE'}")
    print(f"    ACE-Step   (port 8001): {'✅ OK' if ace_ok else '❌ OFFLINE'}")
    print(f"    Ollama     (port 11434): {'✅ OK' if ollama_ok else '❌ OFFLINE'}")

    if evera_ok:
        try:
            status = client.status()
            print(f"    └─ Tracks: {status.get('track_count', '?')}, "
                  f"Artists: {status.get('artist_count', '?')}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 2. Auto-start (if requested or needed for generation)
    # ------------------------------------------------------------------
    if do_start or do_generate:
        print("\n[2] Auto-Start (ensure_evera)")

        if is_evera_ready():
            print("    Already ready — no startup needed")
        else:
            print("    Starting services... (ACE-Step takes ~90-120s to load model)")
            start = time.time()
            ok = ensure_evera(need_lyrics=False)
            elapsed = time.time() - start
            print(f"    Result: {'✅ READY' if ok else '❌ FAILED'} ({elapsed:.0f}s)")

            if ok:
                # Re-check
                ace_ok = client.acestep_healthy()
                print(f"    ACE-Step now: {'✅ OK' if ace_ok else '❌ OFFLINE'}")
            else:
                print("    Cannot proceed with generation — ACE-Step failed to start")
                if not do_generate:
                    return
    elif not ace_ok and not evera_ok:
        print("\n    ⚠️  Services are offline. Run with --start to auto-start.")
        print("       python test_evera.py --start")
        print("       python test_evera.py --generate  (start + test generation)")

    # ------------------------------------------------------------------
    # 3. Discovery
    # ------------------------------------------------------------------
    if evera_ok:
        print("\n[3] Discovery")
        try:
            genres = client.list_genres()
            if isinstance(genres, list):
                names = [g.get('name', g) if isinstance(g, dict) else str(g) for g in genres[:6]]
                print(f"    Genres ({len(genres)}): {', '.join(names)}")
        except Exception as e:
            print(f"    Genres: {e}")

        try:
            artists = client.list_artists()
            if isinstance(artists, list):
                print(f"    Artists: {len(artists)}")
                for a in artists[:3]:
                    name = a.get("name", "?") if isinstance(a, dict) else str(a)
                    print(f"      - {name}")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 4. Generate test track
    # ------------------------------------------------------------------
    if do_generate:
        ace_ok = client.acestep_healthy()
        evera_ok = client.is_healthy()

        if not ace_ok and not evera_ok:
            print("\n[4] ❌ No generation service available — skipping")
        else:
            print("\n[4] Generating test track (30s instrumental)...")
            dest = os.path.join("data", "show_music", "test_gen")
            os.makedirs(dest, exist_ok=True)
            start = time.time()

            try:
                if ace_ok:
                    print("    Using ACE-Step direct...")
                    result = client.acestep_generate(
                        prompt="upbeat electronic synth, bright and energetic, cyberpunk atmosphere",
                        duration=30,
                        dest_dir=dest,
                        timeout=120.0,
                    )
                else:
                    print("    Using EVERA API...")
                    result = client.generate_track(
                        genre="electronic",
                        mood="energetic",
                        theme="upbeat electronic synth, bright and energetic",
                        duration=30,
                        instrumental=True,
                        wait=True,
                        timeout=120.0,
                    )

                elapsed = time.time() - start
                print(f"    ✅ Generation complete in {elapsed:.1f}s")
                audio = result.get('local_path', result.get('audio_url', '?'))
                print(f"    Audio: {audio}")
                if "size_mb" in result:
                    print(f"    Size: {result['size_mb']} MB")

            except EveraClientError as e:
                elapsed = time.time() - start
                print(f"    ❌ Generation failed ({elapsed:.1f}s): {e}")
            except Exception as e:
                elapsed = time.time() - start
                print(f"    ❌ Unexpected error ({elapsed:.1f}s): {e}")

    # ------------------------------------------------------------------
    # 5. Shutdown (if requested)
    # ------------------------------------------------------------------
    if do_shutdown:
        print("\n[5] Shutting down EVERA services...")
        shutdown_evera()
        print("    Done")

    print("\n" + "=" * 60)
    print("  Test complete")
    print("=" * 60)
    if not do_start and not do_generate:
        print("  Flags: --start | --generate | --shutdown")


if __name__ == "__main__":
    main()
