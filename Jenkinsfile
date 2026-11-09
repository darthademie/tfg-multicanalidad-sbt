pipeline {
    // Le dice a Jenkins que ejecute esto en cualquier nodo disponible
    agent any 

    environment {
        // ID de la credencial de Docker Hub
        DOCKERHUB_CREDS = 'dockerhub-darthademie'
        // Imagen del backend en Python
        DOCKER_IMAGE = 'darthademie/tfg-multicanalidad-sbt'
        // Usamos el número de build de Jenkins (1, 2, 3...) como versión única
        TAG = "1.${env.BUILD_NUMBER}"
    }

    stages {
        stage('1. Obtener Código') {
            steps {
                echo 'Descargando código desde GitHub...'
                git branch: 'main', url: 'https://github.com/darthademie/tfg-multicanalidad-sbt.git'
            }
        }

        stage('Pipeline de Integración Continua (CI)') {
            when {
                expression {
                    // 1. Comprobamos si el pipeline se ha lanzado manualmente (por un usuario dándole al botón)
                    def isManualTrigger = currentBuild.rawBuild.getCauses().any { cause ->
                        cause instanceof hudson.model.Cause.UserIdCause
                    }
                    
                    // Si se ha lanzado a mano, saltamos la comprobación y permitimos la ejecución
                    if (isManualTrigger) {
                        echo "[INFO] Compilación lanzada MANUALMENTE. Ignorando comprobación de '[skip ci]'."
                        return true
                    }

                    // 2. Si NO ha sido manual (ej: viene de un Webhook de GitHub), comprobamos el commit
                    def commitMessage = sh(script: 'git log -1 --pretty=%B', returnStdout: true).trim()
                    if (commitMessage.contains('[skip ci]')) {
                        echo "Se ha detectado '[skip ci]' desde un evento automático. Abortando ejecución."
                        currentBuild.result = 'ABORTED'
                        return false
                    }
                    
                    // Si no es manual y no tiene '[skip ci]', permitimos la ejecución
                    return true
                }
            }

            stages {
                stage('2. Análisis de Seguridad Python (Bandit)') {
                    steps {
                        echo 'Lanzando escaneo de vulnerabilidades con Bandit (Shift-Left)...'
                        
                        catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') {
                            sh """
                            set +e 
                            
                            # SOLUCIÓN DooD: Empaquetamos el código y lo enviamos por entrada estándar
                            # al contenedor. Así evitamos el problema de directorios vacíos al usar volúmenes.
                            tar -cf - . | docker run --rm -i python:3.11-slim bash -c "mkdir -p /app && cd /app && tar -xf - && pip install -q bandit && bandit -r . -f txt" > bandit-report.txt
                            
                            BANDIT_EXIT_CODE=\$?
                            
                            echo "=== RESULTADOS DEL ESCANEO DE BANDIT ==="
                            cat bandit-report.txt
                            echo "========================================"
                            
                            exit \$BANDIT_EXIT_CODE
                            """
                        }
                    }
                    post {
                        always {
                            echo 'Archivando reporte de seguridad de Bandit...'
                            archiveArtifacts artifacts: 'bandit-report.txt', allowEmptyArchive: true
                        }
                    }
                }

                stage('3. Construir y Subir a Docker Hub') {
                    steps {
                        withCredentials([usernamePassword(credentialsId: env.DOCKERHUB_CREDS, passwordVariable: 'DOCKERHUB_PASS', usernameVariable: 'DOCKERHUB_USER')]) {
                            echo 'Autenticando en Docker Hub...'
                            sh "echo \$DOCKERHUB_PASS | docker login -u \$DOCKERHUB_USER --password-stdin"
                            
                            echo "Compilando y subiendo ${DOCKER_IMAGE}:${TAG}..."
                            sh "docker build --push -t ${DOCKER_IMAGE}:${TAG} -t ${DOCKER_IMAGE}:latest ."
                        }
                    }
                }

                stage('4. Actualizar Manifiestos (GitOps)') {
                    steps {
                        echo 'Actualizando k8s/tfg-sbt-deployment.yaml para ArgoCD...'
                        
                        withCredentials([usernamePassword(credentialsId: 'github-darthademie', passwordVariable: 'GIT_PASS', usernameVariable: 'GIT_USER')]) {
                            sh """
                            # 1. Configurar identidad de Git
                            git config --global user.email "jenkins@teleupm.com"
                            git config --global user.name "Jenkins CI"
                            
                            # 2. Modificar el archivo YAML del backend
                            sed -i 's|image: darthademie/tfg-multicanalidad-sbt:.*|image: darthademie/tfg-multicanalidad-sbt:${TAG}|g' k8s/teleupm-sbt-deployment.yaml
                            
                            # 3. Hacer Commit y Push
                            git add k8s/teleupm-sbt-deployment.yaml
                            git commit -m "gitops: Despliegue automático de versión ${TAG} [skip ci]"
                            git push https://\$GIT_USER:\$GIT_PASS@github.com/darthademie/tfg-multicanalidad-sbt.git HEAD:main
                            """
                        }
                    }
                }
            }
        }
    }
    post {
        always {
            echo 'Limpiando el workspace de Jenkins...'
            cleanWs()
        }
        success {
            echo "[INFO] Pipeline de Python completado. Imagen subida con éxito como ${TAG}."
        }
        failure {
            echo "[ERROR] El pipeline de Python ha fallado. Revisa la consola para ver los detalles."
        }
    }
}