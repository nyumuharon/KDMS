import https from 'https';
import fs from 'fs';

const url = 'https://data.humdata.org/dataset/02ec0e4c-ec76-4d04-ab4f-801fc1caaa38/resource/820061fa-8a03-455b-af86-d922aeb14cf0/download/ken_admbnda_adm1_iebc_20191031.geojson';
const fallbackUrl = 'https://data.humdata.org/dataset/02ec0e4c-ec76-4d04-ab4f-801fc1caaa38/resource/820061fa-8a03-455b-af86-d922aeb14cf0/download/ken_admbnda_adm1_iebc_20191031.geojson';

function download(url, dest, cb) {
    console.log('Downloading from:', url);
    https.get(url, (res) => {
        if (res.statusCode !== 200) {
            console.log('Failed:', res.statusCode);
            if (url === fallbackUrl) return cb();
            return download(fallbackUrl, dest, cb);
        }
        const file = fs.createWriteStream(dest);
        res.pipe(file);
        file.on('finish', () => {
            file.close(cb);
            console.log('Downloaded successfully to', dest);
        });
    }).on('error', (err) => {
        console.error('Error:', err.message);
    });
}

download(url, './public/kenya-counties.json', () => console.log('Done'));
