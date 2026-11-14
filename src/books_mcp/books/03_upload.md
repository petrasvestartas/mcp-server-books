# Upload to Cloudflare R2

Bucket `brg-books`, AWS CLI profile `r2-books`.

Preview, then upload. No delete, ever.

    E=https://<account>.r2.cloudflarestorage.com
    bash tools/upload-books.sh brg-books $E out/<book>
    bash tools/upload-books.sh brg-books $E out/<book> --upload

Scan PDF goes to `RAW/` (for photo folders, build a compact ~10–30 MiB PDF first with `tools/photos_to_pdf.py` so R2 storage stays small):

    python3 -I tools/photos_to_pdf.py /path/to/photos RAW/Author_Title_Year.pdf --greyscale
    aws --profile r2-books --region auto --endpoint-url $E s3 cp RAW/Author_Title_Year.pdf s3://brg-books/RAW/

Exclude scratch preview directories (`.eqpng/`, `.checks/`, `src/parts/`) when syncing `<book>/` to `s3://brg-books/<book>/`.

Rules: English text, original title beside it, no AI words in published files, third party copyright: ask first.
