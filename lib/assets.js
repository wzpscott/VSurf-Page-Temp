// Load original PLY and JSON assets through the static web server.
export async function readAsset(path, {json = false} = {}) {
    const url = new URL(path, document.baseURI);
    const response = await fetch(url, {cache: 'no-store'});
    if (!response.ok) throw new Error(`Asset unavailable: ${url.pathname}`);
    return json ? response.json() : response.arrayBuffer();
}
