import argparse
import sys
import os
import time

import database
import crawler
import telegram_dispatcher

def cmd_index(args):
    print("🚀 Starting BSEB Class 12th PYQ crawler...")
    t0 = time.time()
    def cb(msg, pct):
        print(f"[{pct*100:5.1f}%] {msg}")
    result = crawler.index_all(progress_callback=cb)
    print(f"✅ Indexing finished in {time.time()-t0:.2f}s!")
    print(f"Total Years: {result['total_years']} | Total Papers: {result['total_papers']}")
    cmd_status(args)

def cmd_resolve(args):
    print("🔍 Pre-resolving direct PDF URLs for all papers...")
    papers = database.get_papers()
    unresolved = [p for p in papers if not p.get('pdf_url')]
    print(f"Found {len(unresolved)} papers requiring PDF URL resolution.")
    
    for idx, p in enumerate(unresolved):
        url = crawler.resolve_pdf_url(p['page_url'])
        if url:
            database.update_paper_pdf_url(p['id'], url)
            print(f"[{idx+1}/{len(unresolved)}] Resolved: {p['clean_filename']} -> {url}")
        else:
            print(f"[{idx+1}/{len(unresolved)}] FAILED to resolve: {p['clean_filename']}")
        time.sleep(0.3)
    print("✅ All PDF URLs resolved!")

def cmd_dispatch(args):
    bot_token = args.token or os.environ.get('TELEGRAM_BOT_TOKEN') or telegram_dispatcher.DEFAULT_BOT_TOKEN
    chat_id = args.chat_id or os.environ.get('TELEGRAM_CHAT_ID') or telegram_dispatcher.DEFAULT_CHAT_ID
    
    if not bot_token:
        print("❌ Error: Telegram Bot Token required. Pass --token or set TELEGRAM_BOT_TOKEN environment variable.")
        sys.exit(1)
        
    print(f"🚀 Starting Telegram Dispatcher to Channel: {chat_id}")
    print(f"Parameters: Year={args.year or 'ALL'}, Order={args.order}, Delay={args.delay}s")
    
    def cb(paper, curr, total):
        print(f"[{curr}/{total}] Processed: {paper['clean_filename']} (Status: {paper['status']})")
        
    stats = telegram_dispatcher.dispatch_batch(
        bot_token=bot_token,
        chat_id=chat_id,
        year=args.year,
        order=args.order,
        delay=args.delay,
        progress_callback=cb
    )
    print(f"✅ Dispatch complete! Sent: {stats['sent']}, Failed: {stats['failed']}")
    cmd_status(args)

def cmd_status(args):
    database.init_db()
    stats = database.get_stats()
    print("")
    print("=======================================================")
    print("📊 BSEB CLASS 12th PYQ DATABASE STATUS")
    print("=======================================================")
    print(f"Total Papers:   {stats['total_papers']}")
    print(f"Sent:           {stats['sent_papers']} ✅")
    print(f"Pending:        {stats['pending_papers']} ⏳")
    print(f"Failed:         {stats['failed_papers']} ❌")
    print(f"Total Years:    {stats['total_years']}")
    print("-------------------------------------------------------")
    print(f"{'Year':<8} | {'Total':<8} | {'Sent':<8} | {'Pending':<8} | {'Failed':<8}")
    print("-------------------------------------------------------")
    for ys in stats['year_stats']:
        print(f"{ys['year']:<8} | {ys['total']:<8} | {ys['sent']:<8} | {ys['pending']:<8} | {ys['failed']:<8}")
    print("=======================================================")
    print("")

def cmd_reset_failed(args):
    database.reset_failed()
    print("✅ Reset all failed papers to 'pending'.")

def main():
    parser = argparse.ArgumentParser(description="BSEB Class 12th PYQ Telegram Automated Dispatcher")
    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")
    
    p_index = subparsers.add_parser("index", help="Index all years and papers into SQLite")
    p_resolve = subparsers.add_parser("resolve", help="Pre-resolve all PDF CDN links")
    
    p_dispatch = subparsers.add_parser("dispatch", help="Send papers to Telegram channel")
    p_dispatch.add_argument("--year", help="Specific year to send (e.g. 2026)")
    p_dispatch.add_argument("--order", default="ASC", choices=["ASC", "DESC"], help="Year order (ASC=2015->2026, DESC=2026->2015)")
    p_dispatch.add_argument("--delay", type=float, default=2.5, help="Delay between messages in seconds")
    p_dispatch.add_argument("--token", help="Telegram Bot Token (or set TELEGRAM_BOT_TOKEN env)")
    p_dispatch.add_argument("--chat_id", help="Telegram Channel Chat ID (or set TELEGRAM_CHAT_ID env)")
    
    p_status = subparsers.add_parser("status", help="Show SQLite stats summary")
    p_reset = subparsers.add_parser("reset-failed", help="Reset failed papers to pending")
    
    args = parser.parse_args()
    if args.command == "index":
        cmd_index(args)
    elif args.command == "resolve":
        cmd_resolve(args)
    elif args.command == "dispatch":
        cmd_dispatch(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "reset-failed":
        cmd_reset_failed(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
