# Upload to Cloudflare R2

Bucket `brg-books`, AWS CLI profile `r2-books`.

Preview, then upload. No delete, ever.

    E=https://<account>.r2.cloudflarestorage.com
    bash tools/upload-books.sh brg-books $E out/<book>
    bash tools/upload-books.sh brg-books $E out/<book> --upload

Scan PDF goes to `RAW/`:

    aws --profile r2-books --region auto --endpoint-url $E s3 cp scan.pdf s3://brg-books/RAW/

Rules: English text, original title beside it, no AI words in published files, third party copyright: ask first.
