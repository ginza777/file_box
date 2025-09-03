#!/bin/bash

# ----- Konfiguratsiya -----
ELASTIC_CONTAINER_NAME="multi-parser-elastic"
ELASTIC_IMAGE="docker.elastic.co/elasticsearch/elasticsearch:8.9.2"
TIKA_JAR_FILE="tika-server-standard-2.6.0.jar"

# ----- Ranglar -----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # Rangsiz

echo -e "${BLUE}🚀 Starting Multi Parser Services...${NC}"

# ----- Yordamchi Funksiyalar -----

# Port bandligini tekshirish
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        return 0 # Band
    else
        return 1 # Bo'sh
    fi
}

# Docker orqali Elasticsearch holatini tekshirish
is_elastic_running() {
    if [ "$(docker ps -q -f "name=${ELASTIC_CONTAINER_NAME}")" ]; then
        return 0 # Ishlayapti
    else
        return 1 # Ishlamayapti
    fi
}

# Tika server holatini tekshirish
is_tika_running() {
    if pgrep -f "java -jar ${TIKA_JAR_FILE}" > /dev/null; then
        return 0 # Ishlayapti
    else
        return 1 # Ishlamayapti
    fi
}

# ----- Asosiy Funksiyalar -----

# Elasticsearch'ni Docker'da ishga tushirish
start_elasticsearch() {
    echo -e "${BLUE}🔍 Starting Elasticsearch via Docker...${NC}"

    if is_elastic_running; then
        echo -e "${GREEN}✅ Elasticsearch is already running in Docker.${NC}"
        return 0
    fi

    # Docker o'rnatilganligini tekshirish
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed. Please install Docker first.${NC}"
        return 1
    fi

    # Docker daemon ishlayotganini tekshirish
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}❌ Docker daemon is not running. Please start the Docker application.${NC}"
        return 1
    fi

    # Agar to'xtatilgan eski container bo'lsa, o'chirib yuborish
    if [ "$(docker ps -aq -f "name=${ELASTIC_CONTAINER_NAME}")" ]; then
        echo -e "${YELLOW}🧹 Removing stopped container '${ELASTIC_CONTAINER_NAME}'...${NC}"
        docker rm "${ELASTIC_CONTAINER_NAME}" > /dev/null
    fi

    echo -e "${YELLOW}⏳ Pulling and starting Elasticsearch container...${NC}"
    # Elasticsearch container'ni orqa fonda ishga tushirish
    docker run -d --name "${ELASTIC_CONTAINER_NAME}" \
        -p 9200:9200 -p 9300:9300 \
        -e "discovery.type=single-node" \
        -e "xpack.security.enabled=false" \
        "${ELASTIC_IMAGE}" > /dev/null

    # Elasticsearch ishga tushishini kutish
    echo -e "${YELLOW}⏳ Waiting for Elasticsearch to become available...${NC}"
    for i in {1..45}; do
        if curl -s http://localhost:9200 > /dev/null 2>&1; then
            echo -e "\n${GREEN}✅ Elasticsearch started successfully on port 9200${NC}"
            return 0
        fi
        sleep 2
        echo -n "."
    done

    echo -e "\n${RED}❌ Failed to start Elasticsearch. Check Docker logs:${NC}"
    echo -e "${YELLOW}   docker logs ${ELASTIC_CONTAINER_NAME}${NC}"
    return 1
}

# Tika serverni ishga tushirish
start_tika_server() {
    echo -e "${BLUE}📄 Starting Tika Server...${NC}"

    if is_tika_running; then
        echo -e "${GREEN}✅ Tika Server is already running.${NC}"
        return 0
    fi

    if [ ! -f "${TIKA_JAR_FILE}" ]; then
        echo -e "${RED}❌ Tika server JAR file not found: ${TIKA_JAR_FILE}${NC}"
        return 1
    fi

    if ! command -v java &> /dev/null; then
        echo -e "${RED}❌ Java is not installed.${NC}"
        return 1
    fi

    # Tika serverni orqa fonda ishga tushirish
    java -jar "${TIKA_JAR_FILE}" > /dev/null 2>&1 &

    echo -e "${YELLOW}⏳ Waiting for Tika Server to start...${NC}"
    for i in {1..30}; do
        # Tika serverning asosiy endpoint'i /tika
        if curl -s http://localhost:9998/tika > /dev/null 2>&1; then
            echo -e "\n${GREEN}✅ Tika Server started successfully on port 9998${NC}"
            return 0
        fi
        sleep 2
        echo -n "."
    done

    echo -e "\n${RED}❌ Failed to start Tika Server.${NC}"
    return 1
}

# Barcha xizmatlarni to'xtatish
stop_services() {
    echo -e "${YELLOW}🛑 Stopping services...${NC}"

    # Elasticsearch container'ni to'xtatish va o'chirish
    if is_elastic_running; then
        echo -e "${YELLOW}   Stopping and removing Elasticsearch container...${NC}"
        docker stop "${ELASTIC_CONTAINER_NAME}" > /dev/null
        docker rm "${ELASTIC_CONTAINER_NAME}" > /dev/null
        echo -e "${GREEN}✅ Elasticsearch stopped${NC}"
    else
        echo -e "${BLUE}   Elasticsearch is not running.${NC}"
    fi

    # Tika serverni to'xtatish
    if is_tika_running; then
        echo -e "${YELLOW}   Stopping Tika Server...${NC}"
        pkill -f "java -jar ${TIKA_JAR_FILE}"
        echo -e "${GREEN}✅ Tika Server stopped${NC}"
    else
        echo -e "${BLUE}   Tika Server is not running.${NC}"
    fi
}

# Xizmatlar holatini ko'rsatish
show_status() {
    echo -e "${BLUE}📊 Service Status:${NC}"

    if is_elastic_running; then
        echo -e "${GREEN}   🔍 Elasticsearch (Docker): Running${NC}"
    else
        echo -e "${RED}   🔍 Elasticsearch (Docker): Not running${NC}"
    fi

    if is_tika_running; then
        echo -e "${GREEN}   📄 Tika Server: Running${NC}"
    else
        echo -e "${RED}   📄 Tika Server: Not running${NC}"
    fi
}



# ----- Skriptning asosiy mantig'i -----
case "${1:-start}" in
    start)
        echo -e "${BLUE}🚀 Starting Multi Parser Services...${NC}"
        if start_elasticsearch && start_tika_server; then
            echo -e "\n${GREEN}🎉 All services started successfully!${NC}"
            echo -e "\n${BLUE}📋 Service URLs:${NC}"
            echo -e "   🔍 Elasticsearch: http://localhost:9200"
            echo -e "   📄 Tika Server: http://localhost:9998"
            echo -e "\n${GREEN}✅ You can now run: python manage.py runserver${NC}"
        else
            echo -e "\n${RED}❌ Failed to start some services. Please check the output above.${NC}"
            exit 1
        fi
        ;;
    stop)
        stop_services
        ;;
    restart)
        echo -e "${BLUE}🔄 Restarting services...${NC}"
        stop_services
        sleep 2
        $0 start
        ;;
    status)
        show_status
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}❌ Unknown command: $1${NC}"
        show_help
        exit 1
        ;;
esac

echo ""