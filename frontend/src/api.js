import axios from "axios";

const url = process.env.NEXT_PUBLIC_API_URL || "http://localhost:4000";

const api = {
    test: async () => {
        const data = await axios.post(
            `${url}/test`,
            {
                method: "POST",
                headers: {
                    'Content-type': 'application-json',
                    'Access-Control-Allow-Origin': '*',
                },
            }
        );
        return data;
    },
    availableData: async (state) => {
        const data = await axios.post(
            `${url}/availableData`,
            { state },
            {
                headers: {
                    'Content-type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
            }
        );
        return data;
    },
    resourceUpload: async (apiData) => {
        console.log(apiData)
        const data = await axios.post(
            `${url}/resourceUpload`,
            apiData,
            {
                headers: {
                    'Access-Control-Allow-Origin': '*',
                },
            }
        );
        return data;
    },
    generateWindBinaries: async (apiData) => {
        const data = await axios.post(
            `${url}/generateWindBinaries`,
            apiData,
            {
                headers: {
                    'Content-type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
            }
        );
        return data;
    },
    portfolioOptimization: async (apiData) => {
        const data = await axios.post(
            `${url}/portfolioOptimization`,
            apiData,
            {
                headers: {
                    'Content-type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
            }
        );
        return data;
    },
    portfolioPlots: async (portfolio) => {
        const data = await axios.post(
            `${url}/portfolioPlots`,
            portfolio,
            {
                headers: {
                    'Content-type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                },
                responseType: 'blob'
            }
        );
        return data;
    },
    // Per-LCOE result endpoints
    listPortfolioPlots: async (portfolioId) => {
        const data = await axios.get(
            `${url}/portfolioResults/${encodeURIComponent(portfolioId)}/plots`,
            { headers: { 'Access-Control-Allow-Origin': '*' } }
        );
        return data;
    },
    getLcoePlot: async (portfolioId, lcoeTarget, plotType) => {
        const data = await axios.get(
            `${url}/portfolioResults/${encodeURIComponent(portfolioId)}/lcoe/${lcoeTarget}/${plotType}`,
            { headers: { 'Access-Control-Allow-Origin': '*' }, responseType: 'blob' }
        );
        return data;
    },
    getPortfolioSummary: async (portfolioId) => {
        const data = await axios.get(
            `${url}/portfolioResults/${encodeURIComponent(portfolioId)}/summary`,
            { headers: { 'Access-Control-Allow-Origin': '*' } }
        );
        return data;
    },
    getEfficientFrontier: async (portfolioId) => {
        const data = await axios.get(
            `${url}/portfolioResults/${encodeURIComponent(portfolioId)}/efficientFrontier`,
            { headers: { 'Access-Control-Allow-Origin': '*' }, responseType: 'blob' }
        );
        return data;
    },
    getStackedCosts: async (portfolioId) => {
        const data = await axios.get(
            `${url}/portfolioResults/${encodeURIComponent(portfolioId)}/stackedCosts`,
            { headers: { 'Access-Control-Allow-Origin': '*' }, responseType: 'blob' }
        );
        return data;
    },
    listPortfolioRuns: async () => {
        const data = await axios.get(
            `${url}/portfolioRuns`,
            { headers: { 'Access-Control-Allow-Origin': '*' } }
        );
        return data;
    },
};

export default api;
